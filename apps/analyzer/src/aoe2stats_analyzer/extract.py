"""Extraction orchestration through the `AnalysisExtractor` Protocol (T365, extended by T655).

Calls `.extract()` and `.events()` on whatever extractor its caller (`run.py`) hands it, and turns
the result into the published-JSON shape `contracts/analysis.md` documents, in the next version
`specs/006-replay-analysis-foundations/contracts/analysis-document.md` defines — nothing else.
**No parser import**: only `packages/core`'s Protocols, value objects and truth types, the
knowledge base's coverage pass, the replay-engine package's pure group-silence computation (which
imports nothing but `packages/core`, so it never loads `aoe2rec_py`) and the standard library. The
concrete extractor is constructed outside this module, by `api/analyze.py`'s composition root.

**Additive only (FR-048).** Every field the version 1 document carried is still at its path with its
type. Four blocks are added — `identity`, `provenance`, `inferred`, `knowledge_gaps` — plus the
`envelope` the wall-clock time moves under. `extracted_at` stays at its old top level too, for one
version, because the web reader requires it there.

**What each added block is.**

- `identity` (FR-040): the six components, via `aoe2stats_core.truth.identity.AnalysisIdentity`,
  which refuses an empty dependency record (FR-044). `engine.deps` and
  `identity.parser_dependencies` are the one record the adapter built from installed distribution
  metadata (T627).
- `provenance` (FR-007, FR-009): one entry per published datum **present** in the document, keyed
  by register datum id, carrying its tier (read from the register, never asserted here), the method
  that produced it as `<id>@<version>`, and its inputs. A datum with no instance in this document
  has no entry; an empty list is not a value.
- `inferred` (FR-010, FR-013): the one inferred datum this feature ships. Each instance carries a
  confidence (a closed level and its basis) and the register's non-claim, and nothing in it is
  worded as a count of losses. Written only when there is at least one episode: an empty list would
  invite being read as "nothing was lost", which no recording can say.
- `knowledge_gaps` (FR-035 to FR-037): the coverage pass's output, verbatim.

**Where a value may be written is structural, not checked afterwards (FR-011, T656).** A datum at
an ordinary document path passes `aoe2stats_core.truth.placement.require_outside_inferred` when
its provenance entry is written, which refuses inferred and predicted; the `inferred` block is
produced only by `placement.inferred_block` from `InferredInstances`, which refuses a stronger
tier, a missing confidence and a dropped non-claim. `validate_document` is the second lock, run by
`run.py` before the object is written. **Canonical serialisation** (T659, FR-041) is
`canonical.py`'s, re-exported here: `canonical_bytes` is what `run.py` stores and `compared_body`
is the same minus the wall-clock set.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, cast

from aoe2stats_analyzer.canonical import WALL_CLOCK_FIELDS, canonical_bytes, compared_body
from aoe2stats_core.replay.analysis import AnalysisExtractor, MatchTimeline, ReplayExtractor
from aoe2stats_core.replay.events import (
    CanonicalEvent,
    CanonicalEventSource,
    EventKind,
    MatchStartedPayload,
)
from aoe2stats_core.truth.identity import AnalysisIdentity
from aoe2stats_core.truth.placement import (
    InferredInstances,
    TierPlacementError,
    inferred_block,
    require_outside_inferred,
)
from aoe2stats_core.truth.provenance import Method
from aoe2stats_core.truth.register import REGISTER
from aoe2stats_core.truth.register import Entry as RegisterEntry
from aoe2stats_core.truth.validate import DocumentInvalid, validate
from aoe2stats_core.truth.validate import Entry as ValidatorEntry
from aoe2stats_knowledge.coverage import coverage
from aoe2stats_knowledge.gaps import KnowledgeGap
from aoe2stats_knowledge.snapshot import Snapshot, snapshot_for
from aoe2stats_replay_engine.silence import GroupSilenceEpisode, compute_group_silence_episodes
from aoe2stats_storage.repositories.knowledge_gaps import (
    WHOLE_BUILD_ENTITY_ID,
    WHOLE_BUILD_ENTITY_KIND,
    WHOLE_BUILD_FIELD,
    GapToRecord,
)

#: `contracts/analysis-document.md`: "`schema_version` increments". Bumped only when the shape of
#: the JSON this module writes changes, never when `MatchTimeline` itself gains a field: the
#: `dataclasses.asdict` conversion in `published_document` below carries every field through by
#: name, so this module has no field list of its own to fall behind.
SCHEMA_VERSION = 2

_SILENCE_DATUM = "participant.group_silence_episodes"
_SILENCE_METHOD = "group-silence.banding@1"

#: FR-040, data-model.md §8: this feature's own version for the coverage pass and the group-silence
#: method. It is **not** a bare number someone has to remember to bump: the banding thresholds are
#: read from the register entry's `method` text (`aoe2stats_replay_engine.silence`), so a threshold
#: edit changes that text and therefore this string, and with it every identity digest — which is
#: what makes a banding change trigger a recompute (FR-042) instead of keeping the same digest.
#: The leading components move by hand when the coverage pass or the banding algorithm itself
#: changes; `tests/test_document_build.py` pins that `_SILENCE_METHOD` is the method the episodes
#: really carry.
ANALYTICS_VERSION = (
    f"coverage@1+{_SILENCE_METHOD}"
    f"+{hashlib.sha256(REGISTER[_SILENCE_DATUM].method.encode('utf-8')).hexdigest()[:12]}"
)

#: The top-level keys that are not register data, exactly the validator's own exempt set
#: (`aoe2stats_core.truth.validate._EXEMPT`) plus the block it reads separately: the wall-clock set
#: and the blocks that describe the document rather than carry values. Presence here has to agree
#: with the validator's, or rule 2 would reject the provenance written below. `schema_version` is
#: register data (`document.schema_version`) and carries its provenance entry (FR-007).
_NOT_REGISTER_DATA = WALL_CLOCK_FIELDS | {"identity", "provenance", "knowledge_gaps", "inferred"}

#: The method behind each family of published datum, by register id prefix. Every published datum
#: with a document path must resolve to one (`_method_for` raises otherwise): a value with no
#: method is exactly what FR-009 forbids, so a datum the register publishes without a method here
#: fails loudly at build time instead of being labelled by default.
_METHODS: tuple[tuple[str, Method], ...] = (
    ("document.", Method("analyzer-constant.write", "1")),
    ("match.", Method("request.copy", "1")),
    ("source_recording.", Method("retention-record.copy", "1")),
    ("engine.", Method("distribution-metadata.read", "1")),
    # Everything the adapter reads out of the recording: `Aoe2RecExtractor.extract`'s fold over the
    # canonical stream (`packages/replay-engine`), the parser's own name and version being in the
    # identity.
    ("participant.", Method("timeline.fold", "1")),
)

# `DocumentInvalid` and `TierPlacementError` are re-exported for `run.py`: the request path may not
# import `aoe2stats_core.truth` itself (FR-049, the 006 boundaries architecture test), and reaches
# the truth types only through this module.
__all__ = [
    "ANALYTICS_VERSION",
    "SCHEMA_VERSION",
    "WALL_CLOCK_FIELDS",
    "DocumentInvalid",
    "TierPlacementError",
    "build_document",
    "canonical_bytes",
    "compared_body",
    "current_identity_digest",
    "extract_timeline",
    "gap_rows",
    "published_document",
    "validate_document",
]


def extract_timeline(extractor: ReplayExtractor, zip_bytes: bytes) -> MatchTimeline:
    """Run one recording through `extractor`, and nothing else.

    No retry, no fallback, no second engine: `extractor.extract` raises `EngineParseError` or
    `MalformedArchiveError` (`aoe2stats_core.replay.validation`, re-exported by
    `aoe2stats_core.replay.analysis`) on a recording it cannot process, and a parse is
    deterministic — a second attempt costs a second, identical failure and another fetch (FR-036,
    constitution V). `run.py` is the one that decides what a raised `ReplayValidationError` means
    for the `match_analyses` row; this function only raises it unchanged.
    """
    return extractor.extract(zip_bytes)


def published_document(
    timeline: MatchTimeline,
    *,
    game_id: int,
    object_key: str,
    zip_sha256: str,
    extracted_at: datetime,
    engine_dependencies: Mapping[str, str],
) -> dict[str, Any]:
    """Every field `contracts/analysis.md` defined, at its path, plus the version 2 `envelope`.

    `MatchTimeline` serialised, plus the provenance that makes FR-041/SC-009a mechanical — which
    retained recording, checksum and all, produced this document, and when — and `engine.deps`, the
    dependency record that used to be an empty literal (FR-044).

    `dataclasses.asdict` is what carries every `MatchTimeline`/`ParticipantTimeline` field through
    unchanged and by name: this function keeps no field list of its own to fall out of sync with
    `packages/core`'s value objects (or, in a test double, with whatever stands in for them, as
    long as it is shaped like a dataclass the same way).

    `extracted_at` is written twice on purpose: under `envelope`, where it belongs, and at its old
    top-level path, which the web reader still requires. Both are the wall-clock set (T659).
    """
    stamp = extracted_at.isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "envelope": {"extracted_at": stamp},
        "game_id": game_id,
        "point_of_view_profile_id": timeline.point_of_view_profile_id,
        "world_time_ms": timeline.world_time_ms,
        "engine": {
            "name": timeline.engine_name,
            "version": timeline.engine_version,
            "deps": dict(engine_dependencies),
        },
        "source_recording": {"object_key": object_key, "sha256": zip_sha256},
        "extracted_at": stamp,
        "participants": _json_native(
            [dataclasses.asdict(participant) for participant in timeline.participants]
        ),
    }


def _json_native(value: Any) -> Any:
    """The value as `json.loads(json.dumps(value))` would return it, without the round trip.

    `dataclasses.asdict` keeps a tuple a tuple and a mapping's integer keys integers, and JSON
    turns the first into a list and the second into strings. The validator reads the document
    *before* it is serialised (T656), and it walks lists, not tuples: an unconverted tuple would be
    one opaque leaf instead of the leaves beneath it. Converting here makes the document the
    validator sees the document the reader parses.
    """
    if isinstance(value, Mapping):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    return value


def build_document(
    extractor: AnalysisExtractor,
    zip_bytes: bytes,
    *,
    game_id: int,
    object_key: str,
    zip_sha256: str,
    extracted_at: datetime,
) -> dict[str, Any]:
    """Parse one recording and build the complete version 2 document. Pure and synchronous.

    The recording is walked twice by the adapter (`extract` for the timeline, `events` for the
    canonical stream) and the stream is materialised once, so the coverage pass, the group-silence
    method and the build lookup all read the same events. A stream is small — the committed
    reference recording yields about eleven thousand — against the parse's own resident memory, so
    this does not move the memory ceiling the adapter guards (R3). Raises what the adapter raises
    on an unparsable recording, and `ValueError` if the dependency record is empty (FR-044); it
    does not validate (T656) and does not serialise (T659).
    """
    timeline = extract_timeline(extractor, zip_bytes)
    events = list(extractor.events(zip_bytes))

    document = published_document(
        timeline,
        game_id=game_id,
        object_key=object_key,
        zip_sha256=zip_sha256,
        extracted_at=extracted_at,
        engine_dependencies=extractor.engine_dependencies,
    )

    gaps = tuple(coverage(events))
    episodes = compute_group_silence_episodes(events)

    identity = AnalysisIdentity(
        recording={"object_key": object_key, "sha256": zip_sha256},
        parser_name=timeline.engine_name,
        parser_version=timeline.engine_version,
        parser_dependencies=extractor.engine_dependencies,
        knowledge=_knowledge_identity(_recording_build(events), gaps),
        analytics=ANALYTICS_VERSION,
    )

    document["identity"] = identity.to_block()
    document["inferred"] = _inferred_block(episodes)
    document["provenance"] = _provenance(document, episodes)
    document["knowledge_gaps"] = [_gap_record(gap) for gap in gaps]
    return document


def validate_document(
    document: Mapping[str, Any], register: Mapping[str, ValidatorEntry] | None = None
) -> None:
    """The one gate (`contracts/analysis-document.md`, "Validation"): delegates to
    `aoe2stats_core.truth.validate.validate` and lets its `DocumentInvalid` propagate unchanged, so
    the failure path records the validator's own message. `register` defaults to the packaged
    register's entries. Running it before the object is written is T656's.
    """
    validate(document, _packaged_register() if register is None else register)


def _packaged_register() -> Mapping[str, ValidatorEntry]:
    # A `non-determinable` entry has no tier, and nothing is ever published at it (data-model.md
    # §1), so the validator's `tier: Tier` is true of every entry kept here.
    return cast(
        "Mapping[str, ValidatorEntry]",
        {entry_id: entry for entry_id, entry in REGISTER.entries.items() if entry.tier is not None},
    )


def _recording_build(events: Iterable[CanonicalEvent]) -> int | None:
    """The game build the recording's own `match-started` event names, or `None` — the same read
    `aoe2stats_knowledge.coverage.coverage` makes, so the two cannot disagree about which build the
    snapshot was resolved for."""
    build: int | None = None
    for event in events:
        if (
            event.kind is EventKind.MATCH_STARTED
            and isinstance(event.payload, MatchStartedPayload)
            and event.payload.build is not None
        ):
            build = event.payload.build
    return build


def _knowledge_identity(build: int | None, gaps: Sequence[KnowledgeGap]) -> dict[str, Any]:
    """The snapshot the analysis names, or the explicit record that none matched (FR-027)."""
    resolved = snapshot_for(build) if build is not None else None
    if isinstance(resolved, Snapshot):
        return _knowledge_record(resolved)
    # The coverage pass reports exactly one whole-build gap when no snapshot can answer, and it is
    # the one that carries the build (`-1` where the stream named none).
    whole_build = next((gap for gap in gaps if gap.cause == "no-snapshot-for-build"), None)
    if whole_build is None:  # pragma: no cover - coverage() always emits it in this case
        raise RuntimeError("no snapshot resolved and the coverage pass reported no gap for it")
    return _knowledge_record(whole_build)


def _knowledge_record(resolved: Snapshot | KnowledgeGap) -> dict[str, Any]:
    """The identity's `knowledge` component for one resolution of a build: the snapshot's own
    four-field identity, or the explicit absence record. The one place its shape is written, so the
    document `build_document` publishes and the digest `current_identity_digest` recomputes cannot
    disagree about it."""
    if isinstance(resolved, Snapshot):
        identity = resolved.identity
        return {
            "source": identity.source,
            "source_version": identity.source_version,
            "describes_build": identity.describes_build,
            "digest": identity.digest,
        }
    return {"absent": resolved.cause, "build": resolved.build}


def current_identity_digest(
    extractor: CanonicalEventSource, stored_document: Mapping[str, Any]
) -> str:
    """The digest this analysis would carry if it were produced **now**, without parsing anything
    (FR-042, T657a).

    The staleness test needs it on every request for a published match, where parsing again is
    exactly what SC-006 forbids. Five of the six identity components are known without the
    recording: the retained recording (immutable once written, so the stored document's own record
    of it is the current one), the parser name, version and dependencies (attributes of the
    running extractor), the analytics version (a constant of this module) and the reconstruction
    marker. The sixth, the knowledge snapshot, depends on the recording's **build**, which only the
    recording names (`match-started`) and which no column of 003's tables holds. The stored
    document already carries it — in its `knowledge` component, as `describes_build` or, for an
    absent snapshot, `build` — and a recording's build cannot change, so the build is read from
    there and resolved against the snapshots installed now. A knowledge refresh of that build
    therefore changes the digest; a build gaining its first snapshot does too.

    Raises `KeyError` or `TypeError` when `stored_document` has no readable identity block, which
    the caller treats as stale, and `ValueError` when the running extractor's dependency record is
    empty (FR-044), the same refusal `build_document` makes.
    """
    stored = stored_document["identity"]
    knowledge = stored["knowledge"]
    build = knowledge["describes_build"] if "describes_build" in knowledge else knowledge["build"]
    return AnalysisIdentity(
        recording=stored["recording"],
        parser_name=extractor.engine_name,
        parser_version=extractor.engine_version,
        parser_dependencies=extractor.engine_dependencies,
        knowledge=_knowledge_record(snapshot_for(build)),
        analytics=ANALYTICS_VERSION,
    ).digest


def _gap_record(gap: KnowledgeGap) -> dict[str, Any]:
    """One gap as the document carries it: the record's own fields, `severity` and `prevents`
    computed by `KnowledgeGap` and copied, never decided here. A whole-build gap names no entity,
    field or civilisation, because nothing about the build is known."""
    entity = {"kind": gap.entity_kind, "id": gap.entity_id} if gap.entity_kind is not None else None
    return {
        "entity": entity,
        "field": gap.field,
        "build": gap.build,
        "civilisation": gap.civilisation,
        "cause": gap.cause,
        "prevents": list(gap.prevents),
        "severity": gap.severity,
    }


def gap_rows(document: Mapping[str, Any]) -> tuple[GapToRecord, ...]:
    """The `analysis_knowledge_gaps` rows for a document: one per entry of its `knowledge_gaps`
    block, read **from the document** (T662).

    The rows are derived from the published list rather than from a second call to the coverage
    pass, so the two cannot disagree: whatever the reader of the document is told is what the
    aggregate report counts. Nothing is recomputed, deduplicated or dropped here (the coverage pass
    already emits at most one gap per unique-index key, T652k/T652v); a gap that names no entity and
    no field — the whole-build `no-snapshot-for-build` gap — is stored under the storage layer's
    whole-build sentinels because those columns are not nullable, and carries `build` as the
    document does, `-1` where the stream named none.
    """
    rows: list[GapToRecord] = []
    for gap in document["knowledge_gaps"]:
        entity = gap["entity"]
        rows.append(
            GapToRecord(
                build=gap["build"],
                entity_kind=WHOLE_BUILD_ENTITY_KIND if entity is None else entity["kind"],
                entity_id=WHOLE_BUILD_ENTITY_ID if entity is None else entity["id"],
                field=WHOLE_BUILD_FIELD if gap["field"] is None else gap["field"],
                civilisation_id=gap["civilisation"],
                cause=gap["cause"],
                severity=gap["severity"],
            )
        )
    return tuple(rows)


def _inferred_block(episodes: Sequence[GroupSilenceEpisode]) -> dict[str, Any]:
    """The `inferred` block (FR-010, FR-011): the only place a value at that tier is written.

    Built through `placement.inferred_block`, whose carrier refuses an instance without a
    confidence or without the non-claim its provenance names, and refuses a provenance stronger
    than inferred. Field names say what was measured. `from_ms` is the match-clock time of the
    group's last command and `until_ms` where the silence stopped being observed; `units` is how
    many unit objects were named together — a size of the group, never a count of anything lost.
    """
    if not episodes:
        return {}
    return dict(
        inferred_block(
            [
                InferredInstances(
                    provenance=episodes[0].provenance,
                    instances=tuple(
                        {
                            "participant": episode.participant,
                            "from_ms": episode.last_commanded_at_ms,
                            "until_ms": episode.silence_ends_at_ms,
                            "units": len(episode.unit_objects),
                            "unit_objects": list(episode.unit_objects),
                            "commanded_together": episode.occurrences,
                            "confidence": {
                                "level": episode.confidence.level.value,
                                "basis": episode.confidence.basis,
                            },
                            "non_claim": episode.non_claim,
                        }
                        for episode in episodes
                    ),
                )
            ]
        )
    )


def _method_for(datum_id: str) -> str:
    for prefix, method in _METHODS:
        if datum_id.startswith(prefix):
            return f"{method.id}@{method.version}"
    raise ValueError(
        f"no method is assigned to published datum {datum_id!r}: a value with no method is not "
        "publishable (FR-009)"
    )


def _leaf_paths(node: Any, path: str) -> Iterable[str]:
    """Each leaf's path: dict keys joined by '.', every list index collapsed to '[]'. The same
    reading as `aoe2stats_core.truth.validate`'s, so presence here is presence there."""
    if isinstance(node, dict):
        if not node and path:
            yield path
        for key, value in node.items():
            yield from _leaf_paths(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        if not node:
            yield f"{path}[]"
        for item in node:
            yield from _leaf_paths(item, f"{path}[]")
    else:
        yield path


def _present(path: str, leaves: frozenset[str]) -> bool:
    """Whether the document carries the register path. A trailing `.*` is the register's wildcard
    for a mapping whose keys are data (`engine.deps.*`, `participants[].age_up_commands.*`): it is
    present when any leaf lies beneath it."""
    if path.endswith(".*"):
        prefix = path[:-1]
        return any(leaf.startswith(prefix) for leaf in leaves)
    return path in leaves


def _provenance(
    document: Mapping[str, Any],
    episodes: Sequence[GroupSilenceEpisode],
    register: Iterable[RegisterEntry] = REGISTER,
) -> dict[str, Any]:
    """FR-007, FR-009: the tier and method of every published datum the document carries.

    The tier is read from the register — nothing here can assert a stronger one (FR-008) — and
    `inputs` are the register's own `depends_on`. A datum the register publishes at an ordinary
    path at inferred or predicted is refused here (FR-011): such a datum has no path, it lives under
    `inferred`.
    """
    leaves = frozenset(
        leaf
        for key, value in document.items()
        if key not in _NOT_REGISTER_DATA
        for leaf in _leaf_paths(value, str(key))
    )
    provenance: dict[str, Any] = {}
    for entry in register:
        if entry.status != "published" or entry.path is None or entry.tier is None:
            continue
        require_outside_inferred(entry.id, entry.tier)
        if _present(entry.path, leaves):
            provenance[entry.id] = {
                "tier": entry.tier.value,
                "method": _method_for(entry.id),
                "inputs": list(entry.depends_on),
            }
    if episodes:
        silence = episodes[0].provenance
        provenance[_SILENCE_DATUM] = {
            "tier": silence.tier.value,
            "method": f"{silence.method.id}@{silence.method.version}",
            "inputs": list(silence.inputs),
        }
    return provenance
