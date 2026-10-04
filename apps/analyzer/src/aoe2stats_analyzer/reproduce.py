"""Reproduction of a published analysis from its recorded identity (T658, FR-043).

`reproduce(identity, ...)` rebuilds the analysis an identity names, or says exactly why it cannot.
There are two honest outcomes and no third: the **same analysis**, or **"cannot reproduce here
because ..."**. Reproducing under a different parser, knowledge snapshot or analytics version and
calling the result the same analysis is the silent rewrite FR-042 forbids, so nothing here falls
back — not to the current parser, not to the snapshot promoted for the build now, not to a
neighbouring snapshot (FR-038).

**What it reads, and nothing else.** The retained recording, by the key the identity records,
through whatever hands it an object store's `get` (`packages/storage`); the snapshot the identity
names, from package data (`aoe2stats_knowledge.snapshot.load_all_snapshots`, which includes the
snapshots a knowledge refresh has demoted — a superseded snapshot is never deleted, SC-005); and the
installed parser and analytics code. It reaches no external source (FR-043, constitution III): it
has no provider, no client and no URL, and it **writes nothing** — the object store it is handed is
typed to the one read it makes, so a write is a type error before it is a bug.

**It reads retained bytes without writing the access-log row (T666m).** 003's FR-029 requires one
`replay_access_log` row for every read of a retained recording, written before the read's result is
used (`run.py`'s `_log_access`). This module has no session and writes nothing, so it writes none.
**Any production caller must write that row itself, before calling `reproduce`.** No caller exists
today: it is exercised by tests only. The first one that is not a test owns the log row, and a
caller that omits it reads retained bytes off the record.

**Refusals, each naming what differs.** Before the recording is touched, the installed code is
compared with the identity, and every difference is collected into one `ReproductionRefused`:

- the parser's name or version, and each dependency that differs, is missing here or is extra here;
- the analytics version. **Decision:** a different installed analytics version is a refusal, not a
  rebuild under the identity's own version. The analytics version names code (the coverage pass and
  the banding method), and this package holds exactly one of it; there is no second implementation
  to run "as of" an older version, so claiming one would be a rebuild by the new code under the old
  name;
- the reconstruction engine marker, which this build never fills in;
- the named snapshot: not installed at all, or installed under the same source, version and build
  with a different digest. A snapshot whose packaged files no longer match their own recorded digest
  is refused by the loader (FR-025), and that refusal is named too.

Then the recording: absent from the store (the store's own `ObjectNotFound`, and nothing else: a
`KeyError` or any other error is a defect or an outage and propagates), or present with a checksum
that is not the one the identity records. A caller-supplied match id that disagrees with the one the
retained key was built from is refused before the store is read, and a rebuilt document the
validator refuses is reported as a refusal naming the validator's reason (T666e). The builder's
own placement refusal (`TierPlacementError`) and the canonical serialiser's refusal (a `ValueError`
raised by `canonical_bytes` alone, not by anything earlier on the path) are refusals too (T666k);
any other error raised while building is a defect or an outage and propagates. Last, **the built
analysis must carry the identity it was asked for**: its identity digest is compared with the
requested one and a mismatch names the components that differ.
That check is what makes "identical" a measured outcome rather than a hope — it covers the one case
the checks above cannot, an identity whose knowledge is the explicit absence of a snapshot for the
build, and a snapshot that has since been promoted for that build.

**Returns** `canonical_bytes` of the rebuilt document, the same serialisation `run.py` stores. Its
wall-clock set (the envelope and the legacy `extracted_at`) is the time of this reproduction, and is
the one part outside what is compared (`compared_body`, FR-041): a reproduction run later cannot
carry the first run's clock without storing it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aoe2stats_analyzer.extract import (
    ANALYTICS_VERSION,
    DocumentInvalid,
    TierPlacementError,
    build_document,
    canonical_bytes,
    validate_document,
)
from aoe2stats_core.replay.analysis import AnalysisExtractor
from aoe2stats_core.truth.identity import NOT_APPLICABLE, AnalysisIdentity
from aoe2stats_knowledge.snapshot import (
    Snapshot,
    SnapshotError,
    load_all_snapshots,
    pinned_snapshot,
)
from aoe2stats_storage.objects import ObjectNotFound, ObjectReader, retained_recording_object_key

__all__ = ["RecordingSource", "ReproductionRefused", "reproduce"]

#: The four fields a snapshot is named by (`SnapshotIdentity`), as the identity records them.
_SNAPSHOT_FIELDS = ("source", "source_version", "describes_build", "digest")

#: The one thing reproduction asks of an object store: read an object. No `put`, no `delete`.
RecordingSource = ObjectReader


class ReproductionRefused(Exception):
    """The identity cannot be reproduced here. `reasons` is each thing that is missing or
    different, one sentence each; the message is all of them."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons: tuple[str, ...] = tuple(reasons)
        super().__init__("cannot reproduce here because: " + "; ".join(self.reasons))


async def reproduce(
    identity: AnalysisIdentity,
    *,
    object_store: RecordingSource,
    extractor: AnalysisExtractor,
    game_id: int | None = None,
) -> bytes:
    """The canonical bytes of the analysis `identity` names, or `ReproductionRefused`.

    `game_id` is the match the analysis is of. The identity records the recording's key and
    checksum and no match id, yet the document carries one (`game_id`, part of what is compared), so
    it is a caller's input; left out, it is read back from the key through the one function that
    writes keys (`retained_recording_object_key`) and the identity is refused if that round trip
    does not hold — never defaulted, which would make the document differ in a field no digest
    covers.

    **Reads retained bytes and writes no access-log row** (module docstring, FR-029): a production
    caller must write the `replay_access_log` row before calling this. No caller exists today.

    Raises `ReproductionRefused` for every case the module docstring lists; a recording that
    verifies but cannot be parsed raises what the extractor raises, and an object-store failure
    other than "no such object" propagates unchanged — an outage is not a reason to say an analysis
    cannot be reproduced.
    """
    reasons = _installed_code_differences(identity, extractor)
    named, snapshot_reasons = _named_snapshot(identity)
    reasons.extend(snapshot_reasons)
    if reasons:
        raise ReproductionRefused(reasons)

    object_key, recorded_sha256 = _recording_record(identity)
    if game_id is not None:
        _check_game_id_against_key(game_id, object_key)
    zip_bytes = await _read_recording(object_store, object_key)
    actual_sha256 = hashlib.sha256(zip_bytes).hexdigest()
    if actual_sha256 != recorded_sha256:
        raise ReproductionRefused(
            [
                f"the retained recording {object_key!r} has sha256 {actual_sha256}, but the "
                f"identity records {recorded_sha256}"
            ]
        )

    document = _build(
        extractor,
        zip_bytes,
        game_id=game_id if game_id is not None else _game_id_from_key(object_key),
        object_key=object_key,
        sha256=recorded_sha256,
        named=named,
    )
    built = document["identity"]
    if built["digest"] != identity.digest:
        raise ReproductionRefused(_component_differences(identity, built))
    try:
        return canonical_bytes(document)
    except ValueError as exc:
        # The serialiser refuses what JSON cannot spell (a non-finite float) or two keys that
        # collide; it is a deliberate refusal of this document, the third place one is made.
        raise ReproductionRefused(
            [f"the analysis rebuilt here cannot be serialised canonically ({exc})"]
        ) from exc


def _build(
    extractor: AnalysisExtractor,
    zip_bytes: bytes,
    *,
    game_id: int,
    object_key: str,
    sha256: str,
    named: Snapshot | None,
) -> dict[str, Any]:
    # The pin is the only way the named snapshot reaches the build, and it is entered only for a
    # snapshot the identity named: for an identity naming none, the build resolves as it always
    # does and the digest comparison in `reproduce` decides whether that is the same analysis.
    # Synchronous, like `run.py`'s own call: the parse is CPU-bound, and the pin is a context var.
    def build() -> dict[str, Any]:
        try:
            document = build_document(
                extractor,
                zip_bytes,
                game_id=game_id,
                object_key=object_key,
                zip_sha256=sha256,
                extracted_at=datetime.now(UTC),
            )
        except TierPlacementError as exc:
            # The builder's own lock: it refused to place a datum where its tier does not belong.
            raise ReproductionRefused(
                [f"the analysis cannot be rebuilt here: the builder refused a placement ({exc})"]
            ) from exc
        try:
            validate_document(document)
        except DocumentInvalid as exc:
            # The contract has two outcomes, identical or "cannot reproduce here because": a
            # document this installed code cannot publish is the second, with the validator's text.
            raise ReproductionRefused(
                [f"the analysis rebuilt here is refused by the document validator ({exc})"]
            ) from exc
        return document

    if named is None:
        return build()
    with pinned_snapshot(named):
        return build()


def _retained_key_game_id(object_key: str) -> int | None:
    """The match id a retained recording's key was built from, checked by rebuilding the key; `None`
    for a key that is not a retained-recording key."""
    parts = object_key.split("/")
    if len(parts) == 3 and parts[1].isdigit() and parts[2].removesuffix(".zip").isdigit():
        game_id, profile_id = int(parts[1]), int(parts[2].removesuffix(".zip"))
        if retained_recording_object_key(game_id, profile_id) == object_key:
            return game_id
    return None


def _game_id_from_key(object_key: str) -> int:
    game_id = _retained_key_game_id(object_key)
    if game_id is None:
        raise ReproductionRefused(
            [
                f"the match id cannot be read from the recording key {object_key!r}: "
                "it is not a retained-recording key, and none was given"
            ]
        )
    return game_id


def _check_game_id_against_key(game_id: int, object_key: str) -> None:
    """A supplied match id is an input no digest covers, so it is checked against the one place the
    identity records it: the key. A key that is not a retained-recording key records no match, and
    the caller's id stands."""
    from_key = _retained_key_game_id(object_key)
    if from_key is not None and from_key != game_id:
        raise ReproductionRefused(
            [
                f"the match id {game_id} was given, but the retained recording key "
                f"{object_key!r} was built for match {from_key}"
            ]
        )


def _installed_code_differences(
    identity: AnalysisIdentity, extractor: AnalysisExtractor
) -> list[str]:
    reasons: list[str] = []
    if extractor.engine_name != identity.parser_name:
        reasons.append(
            f"the identity names parser {identity.parser_name!r}, "
            f"but the installed parser is {extractor.engine_name!r}"
        )
    elif extractor.engine_version != identity.parser_version:
        reasons.append(
            f"the identity names parser {identity.parser_name} {identity.parser_version}, "
            f"but the installed version is {extractor.engine_version}"
        )
    reasons.extend(_dependency_differences(identity.parser_dependencies, extractor))
    if identity.analytics != ANALYTICS_VERSION:
        reasons.append(
            f"the identity names analytics version {identity.analytics!r}, "
            f"but the installed analytics version is {ANALYTICS_VERSION!r}"
        )
    if identity.reconstruction_engine != NOT_APPLICABLE:
        reasons.append(
            f"the identity names reconstruction engine {identity.reconstruction_engine!r}, "
            "which is not installed here"
        )
    return reasons


def _dependency_differences(recorded: Mapping[str, str], extractor: AnalysisExtractor) -> list[str]:
    installed: Mapping[str, str] = getattr(extractor, "engine_dependencies", {})
    reasons: list[str] = []
    for name in sorted(recorded.keys() | installed.keys()):
        if name not in installed:
            reasons.append(
                f"parser dependency {name} {recorded[name]} is named by the identity "
                "but is not installed here"
            )
        elif name not in recorded:
            reasons.append(
                f"parser dependency {name} {installed[name]} is installed here "
                "but the identity does not name it"
            )
        elif recorded[name] != installed[name]:
            reasons.append(
                f"parser dependency {name} is {recorded[name]} in the identity "
                f"but {installed[name]} here"
            )
    return reasons


def _named_snapshot(identity: AnalysisIdentity) -> tuple[Snapshot | None, list[str]]:
    """The installed snapshot the identity names, resolved among **every** packaged snapshot by its
    four-field identity — never by build, which would answer with whichever is promoted now."""
    knowledge = identity.knowledge
    if "absent" in knowledge and "digest" not in knowledge:
        return None, []
    missing = [name for name in _SNAPSHOT_FIELDS if name not in knowledge]
    if missing:
        return None, [
            "the identity's knowledge names neither a snapshot nor the absence of one "
            f"(missing {', '.join(missing)})"
        ]
    try:
        installed = load_all_snapshots()
    except SnapshotError as exc:
        return None, [f"an installed knowledge snapshot fails its own verification: {exc}"]

    wanted = {name: knowledge[name] for name in _SNAPSHOT_FIELDS}
    same_name = [
        snapshot
        for snapshot in installed
        if (
            snapshot.identity.source == wanted["source"]
            and snapshot.identity.source_version == wanted["source_version"]
            and snapshot.identity.describes_build == wanted["describes_build"]
        )
    ]
    for snapshot in same_name:
        if snapshot.identity.digest == wanted["digest"]:
            return snapshot, []
    label = f"{wanted['source']} {wanted['source_version']} (build {wanted['describes_build']})"
    if same_name:
        digests = ", ".join(snapshot.identity.digest for snapshot in same_name)
        return None, [
            f"the knowledge snapshot {label} is installed with digest {digests}, "
            f"but the identity names digest {wanted['digest']}"
        ]
    return None, [f"the knowledge snapshot {label} with digest {wanted['digest']} is not installed"]


def _recording_record(identity: AnalysisIdentity) -> tuple[str, str]:
    record = identity.recording
    missing = [name for name in ("object_key", "sha256") if not record.get(name)]
    if missing:
        raise ReproductionRefused(
            [f"the identity's recording does not record its {', '.join(missing)}"]
        )
    return str(record["object_key"]), str(record["sha256"])


async def _read_recording(object_store: RecordingSource, object_key: str) -> bytes:
    try:
        return await object_store.get(object_key)
    except ObjectNotFound:
        raise ReproductionRefused(
            [f"the retained recording {object_key!r} is not in the object store"]
        ) from None


def _component_differences(identity: AnalysisIdentity, built: Mapping[str, Any]) -> list[str]:
    requested = identity.to_block()
    differing = [
        name for name in requested if name != "digest" and requested[name] != built.get(name)
    ]
    return [
        f"the analysis rebuilt here carries a different identity ({name}: the identity names "
        f"{requested[name]!r}, the rebuild has {built.get(name)!r})"
        for name in differing
    ] or ["the analysis rebuilt here carries a different identity digest"]
