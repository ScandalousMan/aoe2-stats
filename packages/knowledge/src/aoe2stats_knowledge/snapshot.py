"""A knowledge snapshot's identity, its digest and load-time verification (FR-024, FR-025).

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "Identity and immutability". Data model:
[data-model.md](../../../../specs/006-replay-analysis-foundations/data-model.md) §6.

A snapshot's identity is its ``source``, that source's own ``source_version``, the game build it
``describes_build``, and a ``digest`` over its canonical content — ``rules.json`` and
``effects.toml`` — recorded in the snapshot's ``snapshot.toml``. On load the digest is recomputed
from the packaged files and compared; a mismatch refuses to load rather than serving content that
no longer matches what was recorded (FR-025's "never modified or removed" is asserted here, at
every load, not merely at publish time — publish-time enforcement is the promotion sequence below).

Every snapshot directory is read through :mod:`importlib.resources`, never a bare filesystem path,
so the same code resolves a snapshot identically whether the package is installed from a wheel (a
serverless bundle) or run from an editable checkout (a virtual environment). ``packages/knowledge/
snapshots/`` sits beside ``src/`` rather than inside it, so that it is easy to find and review as
vendored-adjacent, git-tracked data; ``pyproject.toml``'s ``force-include`` maps it into the wheel
at ``aoe2stats_knowledge/snapshots`` for a real build, and ``src/aoe2stats_knowledge/snapshots`` is
a checked-in symlink back to it for the editable/dev case — both resolve to the identical tree
through the identical anchor, ``importlib.resources.files("aoe2stats_knowledge") / "snapshots"``.

**Promotion (FR-034, FR-030)**: `snapshot.toml`'s `[snapshot]` table also carries `promoted`, a
boolean defaulting to `False` when absent, and an optional `[validation]` table recording what was
checked, against what, by whom and when (FR-030's "the validation performed MUST be recorded").
Setting `promoted = true` with no `[validation]` table, or an empty one, is refused at load time
with `SnapshotPromotionError` — FR-034's "MUST NOT promote an unvalidated snapshot" is an invariant
enforced here, not a convention left to whoever writes the next `snapshot.toml`. Only a promoted
snapshot is resolvable by build: `load_resolvable_snapshots` is the set `snapshot_for(build)`
resolves against, distinct from `load_all_snapshots`, which loads every digest-verified snapshot
whether or not it is promoted.

**Carry-forward (T642, research.md D4, FR-030, FR-034)**: a `[validation]` table whose `method` is
`"carry-forward"` carries, inside `ValidationRecord.details["carry_forward"]`, the source's own
last-implemented build, the evidence for that claim, and the ordered list of every build between it
and `describes_build` (inclusive) — `intervening_builds` — each with a matching per-build
attestation in `builds`: the notes consulted, where they were read, the date, and the reading
(`_CARRY_FORWARD_BUILD_FIELDS`). `_check_carry_forward_completeness` enforces this structurally, at
parse time, the same way `parse_promotion` already refuses an empty `[validation]` table regardless
of `promoted` — a carry-forward record naming a build with no attestation, or attesting a build it
never declared, is malformed, not merely unfinished, and raises `SnapshotCarryForwardIncomplete`
(a `SnapshotPromotionError`) or `SnapshotError` rather than loading a record that looks complete but
has a hole a later build could hide behind. What this cannot check is whether `intervening_builds`
itself is true to the game's real build history — that is the transcriber's claim, carried as data
(`source_last_implemented_build_evidence`) and reviewed like any other FR-031 transcription, not a
fact this module has an independent way to verify.

**Build resolution (FR-027, T641)**: `snapshot_for(build)` is an exact match on `describes_build`
among `load_resolvable_snapshots()` — promotion still gates resolvability, so an unpromoted
snapshot never resolves even when its `describes_build` matches. There is no nearest, no latest and
no fallback parameter: the function takes exactly one required parameter, and
`test_snapshot_for_accepts_exactly_one_required_parameter` asserts that structurally, so a later
edit adding a `strategy=`/`allow_nearest=` parameter fails loudly rather than silently reintroducing
the substitution FR-027 forbids. A build with no promoted snapshot returns `NoSnapshotForBuild`
rather than `None` or a raised exception — a gap is data, not a control-flow signal.

`NoSnapshotForBuild` is a **deliberately minimal, interim** gap value, not the `KnowledgeGap` FR-035
to FR-037 describe (entity, field, affected civilisation, "what it prevents", a computed severity).
`snapshot_for` is asked only for a build — it has no entity, field or civilisation to name — so it
cannot construct that richer record itself. **T647, when it implements `gaps.py`'s full
`KnowledgeGap`, must decide how this call site's result folds into that type** (wrapping it,
subsuming its one field, or replacing this class outright) rather than leaving two parallel gap
vocabularies in the package. `cause="no-snapshot-for-build"` is the literal
contracts/knowledge-base.md, "Resolution by build" already names, so T647's closed cause set must
include it unchanged.
"""

from __future__ import annotations

import hashlib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Final

#: The package this module's data is anchored to. Never a filesystem path: `importlib.resources`
#: resolves it the same way whether installed from a wheel or run from an editable checkout.
_PACKAGE: Final[str] = "aoe2stats_knowledge"

#: `snapshot.toml`'s own filename, inside each snapshot directory.
IDENTITY_FILENAME: Final[str] = "snapshot.toml"

#: The two files the digest is computed over, in this fixed order (contracts/knowledge-base.md,
#: "Identity and immutability": "the digest is recomputed over rules.json and effects.toml").
DIGESTED_FILENAMES: Final[tuple[str, str]] = ("rules.json", "effects.toml")


class SnapshotError(ValueError):
    """A packaged snapshot could not be loaded: malformed identity or, most importantly, a
    digest that no longer matches its recorded one (FR-025)."""


class SnapshotDigestMismatch(SnapshotError):
    """The digest recomputed from `rules.json` and `effects.toml` disagrees with the digest
    recorded in `snapshot.toml`. Raised in place of returning a `Snapshot` — there is no partial
    or best-effort load, because a mismatch is exactly the condition FR-025 exists to catch."""


class SnapshotPromotionError(SnapshotError):
    """`promoted = true` was set in `snapshot.toml` with no `[validation]` table, or an empty one
    (FR-034: "MUST NOT promote an unvalidated snapshot"). Raised at load time in place of
    constructing a `Snapshot` whose `promoted` flag would be true without the FR-030 record that
    is supposed to justify it — the invariant is enforced where the flag is read, not left to
    whoever writes the next `snapshot.toml` to remember."""


class SnapshotCarryForwardIncomplete(SnapshotPromotionError):
    """A `[validation]` table with `method = "carry-forward"` does not attest every build between
    the source revision's own last-implemented build and `describes_build` (research.md D4: "a
    build with no entry in that list makes the snapshot unpromotable"). Raised, like a missing
    `[validation]` table, regardless of `promoted` — a carry-forward record with a hole is
    malformed for its own declared method, not merely a validation not yet performed."""


#: The FR-030 fields every validation record must carry, regardless of `method`. Anything else a
#: `[validation]` table carries (T642's per-build carry-forward note list, for one) lands in
#: `ValidationRecord.details` instead of a dedicated field, so a new validation method never
#: requires extending this tuple or the dataclass below.
_VALIDATION_REQUIRED_FIELDS: Final[tuple[str, str, str, str]] = (
    "method",
    "checked_against",
    "performed_by",
    "performed_at",
)

#: research.md D4's four per-build attestation fields, inside each
#: `[[validation.carry_forward.builds]]` entry: the notes consulted, where they were read, the
#: date, and the reading (what the notes said — did anything the pack carries change?).
_CARRY_FORWARD_BUILD_FIELDS: Final[tuple[str, str, str, str]] = (
    "notes_consulted",
    "read_at",
    "date_read",
    "reading",
)


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    """FR-030's validation record: what was checked (`method`), against what (`checked_against`
    — "the game" or a named second source), by whom (`performed_by`) and when (`performed_at`).

    `method` is open text on purpose (e.g. `"carry-forward"`, `"second-source"`,
    `"game-comparison"`) — this dataclass encodes only the shell FR-030 requires of every
    validation, not any one method's internal shape. `details` carries every other key the
    `[validation]` table has: T642 is expected to add carry-forward's per-build note list (the
    notes consulted, where, when, and the reading, for every intervening build — research.md D4)
    there, so a new validation method's content never requires redesigning this dataclass or the
    promotion invariant `parse_promotion` enforces.
    """

    method: str
    checked_against: str
    performed_by: str
    performed_at: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("method", self.method),
            ("checked_against", self.checked_against),
            ("performed_by", self.performed_by),
            ("performed_at", self.performed_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SnapshotError(
                    f"[validation].{field_name} must be a non-blank string, got {value!r}"
                )


@dataclass(frozen=True, slots=True)
class SnapshotIdentity:
    """FR-024's four-field identity: a knowledge source, that source's own version, the game
    build the snapshot describes, and a digest of its canonical content."""

    source: str
    source_version: str
    describes_build: int
    digest: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source", self.source),
            ("source_version", self.source_version),
            ("digest", self.digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SnapshotError(f"{field_name} must be a non-blank string, got {value!r}")
        if not isinstance(self.describes_build, int) or isinstance(self.describes_build, bool):
            raise SnapshotError(f"describes_build must be an int, got {self.describes_build!r}")
        if not self.digest.startswith("sha256:") or len(self.digest) != len("sha256:") + 64:
            raise SnapshotError(
                f"digest must be a 'sha256:'-prefixed 64-character hex digest, got {self.digest!r}"
            )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One packaged knowledge snapshot, verified against its own content on load.

    `directory` is the snapshot's directory name under the packaged `snapshots/` root, `identity`
    is its FR-024 identity, `promoted` is FR-034's flag (never true without `validation` set — see
    `parse_promotion`), and `validation` is the FR-030 record `promoted` depends on, or `None` for
    a snapshot that has not been validated at all. T640 extends this dataclass with the normalised
    rules body it carries.
    """

    directory: str
    identity: SnapshotIdentity
    promoted: bool = False
    validation: ValidationRecord | None = None


def compute_digest(rules_json: bytes, effects_toml: bytes) -> str:
    """The FR-024 digest over a snapshot's canonical content: `rules.json` then `effects.toml`.

    Each file is hashed with its name and byte length as an unambiguous prefix, so the two files
    cannot be shuffled or truncated into producing the same digest as a different pair of
    contents. Returned as `"sha256:" + hex digest`, the same shape `MANIFEST.json` already uses
    for a pack's own per-file digests.
    """
    hasher = hashlib.sha256()
    for filename, content in zip(DIGESTED_FILENAMES, (rules_json, effects_toml), strict=True):
        hasher.update(filename.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return f"sha256:{hasher.hexdigest()}"


def _snapshots_root() -> resources.abc.Traversable:
    """The packaged `snapshots/` root, resolved through `importlib.resources` alone."""
    return resources.files(_PACKAGE).joinpath("snapshots")


def list_snapshot_directories() -> tuple[str, ...]:
    """Every directory committed under the packaged `snapshots/` root, sorted by name.

    Never a bare filesystem walk: this is the same `importlib.resources` traversal `load_snapshot`
    uses, so a snapshot that is invisible to one is invisible to the other.
    """
    root = _snapshots_root()
    if not root.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in root.iterdir() if entry.is_dir()))


def _require_table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SnapshotError(f"snapshot.toml: missing or malformed [{key}] table")
    return value


def _require_str(table: Mapping[str, Any], key: str, *, table_name: str = "snapshot") -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SnapshotError(f"snapshot.toml: [{table_name}].{key} must be a non-blank string")
    return value


def _require_int(table: Mapping[str, Any], key: str) -> int:
    value = table.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SnapshotError(f"snapshot.toml: [snapshot].{key} must be an integer")
    return value


def _load_toml(snapshot_toml_text: str) -> Mapping[str, Any]:
    try:
        return tomllib.loads(snapshot_toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise SnapshotError(f"snapshot.toml is not valid TOML: {exc}") from exc


def parse_identity(snapshot_toml_text: str) -> SnapshotIdentity:
    """Parse `snapshot.toml`'s `[snapshot]` table into a `SnapshotIdentity`.

    Reads exactly the four FR-024 fields and ignores every other key `snapshot.toml` may carry
    (`promoted`, `civilisations_modelled`, a `[validation]` table): those belong to the promotion
    sequence `parse_promotion` reads, not this function's identity mechanism, and a table that
    carries them is not malformed.
    """
    data = _load_toml(snapshot_toml_text)
    table = _require_table(data, "snapshot")
    return SnapshotIdentity(
        source=_require_str(table, "source"),
        source_version=_require_str(table, "source_version"),
        describes_build=_require_int(table, "describes_build"),
        digest=_require_str(table, "digest"),
    )


def _parse_validation_record(table: Mapping[str, Any]) -> ValidationRecord:
    """Build a `ValidationRecord` from a non-empty `[validation]` table.

    The four FR-030 fields are read strictly (`SnapshotError` if any is missing or blank); every
    other key the table carries — T642's per-build carry-forward notes, for instance — is kept
    verbatim in `details` rather than dropped, so a validation method this module does not know
    about is not silently truncated.
    """
    details = {key: value for key, value in table.items() if key not in _VALIDATION_REQUIRED_FIELDS}
    return ValidationRecord(
        method=_require_str(table, "method", table_name="validation"),
        checked_against=_require_str(table, "checked_against", table_name="validation"),
        performed_by=_require_str(table, "performed_by", table_name="validation"),
        performed_at=_require_str(table, "performed_at", table_name="validation"),
        details=details,
    )


def _require_carry_forward_build_list(value: Any, *, key: str) -> tuple[int, ...]:
    """`[validation.carry_forward].intervening_builds` (or any similarly-shaped list): a non-empty,
    strictly ascending, duplicate-free tuple of build numbers. Raised as `SnapshotError` — this is
    a shape problem, not the "a declared build has no attestation" problem
    `SnapshotCarryForwardIncomplete` names."""
    if not isinstance(value, list) or not value:
        raise SnapshotError(
            f"[validation.carry_forward].{key} must be a non-empty list of build numbers, "
            f"got {value!r}"
        )
    builds: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise SnapshotError(
                f"[validation.carry_forward].{key} entries must be integers, got {item!r}"
            )
        builds.append(item)
    if builds != sorted(builds) or len(set(builds)) != len(builds):
        raise SnapshotError(
            f"[validation.carry_forward].{key} must be strictly ascending with no duplicates, "
            f"got {builds!r}"
        )
    return tuple(builds)


def _check_carry_forward_completeness(validation: ValidationRecord, describes_build: int) -> None:
    """research.md D4's invariant, enforced structurally, for a `method = "carry-forward"`
    validation record (T642).

    A carry-forward record must declare, in `details["carry_forward"]`:

    - `source_last_implemented_build` (int): the source revision's own newest build.
    - `intervening_builds` (list[int]): every build between it and `describes_build`, ascending,
      ending in `describes_build` itself — the set this carry-forward has to cover.
    - `builds` (list of tables): one per-build attestation for each entry in `intervening_builds`,
      each carrying `_CARRY_FORWARD_BUILD_FIELDS` — the notes consulted, where they were read, the
      date, and the reading — all non-blank.

    A build declared in `intervening_builds` with no matching `builds` entry raises
    `SnapshotCarryForwardIncomplete` naming which build is missing. A `builds` entry for a build
    *not* declared in `intervening_builds` is equally refused (as a plain `SnapshotError`): an
    attestation the record does not also claim as required proves nothing about completeness.

    This does not, and cannot, verify that `intervening_builds` is itself the *true* complete set
    of builds the source has not implemented — that is the transcriber's own claim, carried as data
    (`source_last_implemented_build_evidence`) for a reviewer to check, exactly as FR-031 already
    expects of any human transcription. What is enforced here is that the record cannot claim
    coverage it does not also attest.
    """
    if validation.method != "carry-forward":
        return
    carry_forward = validation.details.get("carry_forward")
    if not isinstance(carry_forward, dict):
        raise SnapshotCarryForwardIncomplete(
            '[validation] method = "carry-forward" requires a [validation.carry_forward] table '
            "naming source_last_implemented_build, intervening_builds and a per-build builds list "
            "(research.md D4)"
        )
    source_last_implemented_build = carry_forward.get("source_last_implemented_build")
    if not isinstance(source_last_implemented_build, int) or isinstance(
        source_last_implemented_build, bool
    ):
        raise SnapshotError(
            "[validation.carry_forward].source_last_implemented_build must be an integer, got "
            f"{source_last_implemented_build!r}"
        )
    intervening_builds = _require_carry_forward_build_list(
        carry_forward.get("intervening_builds"), key="intervening_builds"
    )
    if intervening_builds[0] <= source_last_implemented_build:
        raise SnapshotError(
            "[validation.carry_forward].intervening_builds must all be later than "
            f"source_last_implemented_build ({source_last_implemented_build}), "
            f"got {intervening_builds!r}"
        )
    if intervening_builds[-1] != describes_build:
        raise SnapshotError(
            "[validation.carry_forward].intervening_builds must end with describes_build "
            f"({describes_build}), got {intervening_builds!r}"
        )
    builds_table = carry_forward.get("builds")
    if not isinstance(builds_table, list) or not builds_table:
        raise SnapshotCarryForwardIncomplete(
            "[validation.carry_forward].builds must be a non-empty list of per-build attestations"
        )
    attested: dict[int, Mapping[str, Any]] = {}
    for entry in builds_table:
        if not isinstance(entry, dict):
            raise SnapshotError("[validation.carry_forward].builds entries must be tables")
        build = entry.get("build")
        if not isinstance(build, int) or isinstance(build, bool):
            raise SnapshotError(
                "[validation.carry_forward].builds entries must carry an integer 'build', "
                f"got {build!r}"
            )
        if build in attested:
            raise SnapshotError(
                f"[validation.carry_forward].builds carries more than one entry for build {build}"
            )
        for field_name in _CARRY_FORWARD_BUILD_FIELDS:
            value = entry.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise SnapshotCarryForwardIncomplete(
                    f"[validation.carry_forward].builds entry for build {build} is missing a "
                    f"non-blank {field_name!r} (research.md D4: the notes consulted, where they "
                    "were read, the date, and the reading)"
                )
        attested[build] = entry
    missing = [build for build in intervening_builds if build not in attested]
    if missing:
        raise SnapshotCarryForwardIncomplete(
            f"carry-forward validation record is missing an attestation for build(s) {missing} "
            f"— every build between source_last_implemented_build "
            f"({source_last_implemented_build}) and describes_build ({describes_build}) must be "
            "listed with its notes consulted, where, when and the reading (research.md D4)"
        )
    extra = sorted(set(attested) - set(intervening_builds))
    if extra:
        raise SnapshotError(
            f"[validation.carry_forward].builds attests build(s) {extra} not declared in "
            "intervening_builds — an attestation for a build the record does not also claim as "
            "required to cover is not evidence of completeness"
        )


def parse_promotion(snapshot_toml_text: str) -> tuple[bool, ValidationRecord | None]:
    """Parse `snapshot.toml`'s FR-034 promotion flag and its FR-030 validation record.

    `[snapshot].promoted` defaults to `False` when absent — an omitted flag is not a promotion.
    A `[validation]` table that is absent, or present with no keys at all, is "no validation
    recorded" and parses to `None`; a `[validation]` table that is present but missing one of the
    four required fields is malformed and raises `SnapshotError` regardless of `promoted`, because
    a partial validation record is not the same thing as none at all. `method = "carry-forward"`
    is checked the same way, by the same discipline (T642, research.md D4): its
    `[validation.carry_forward]` content must attest every build it declares as needing coverage,
    regardless of `promoted` — see `_check_carry_forward_completeness`. Setting `promoted = true`
    together with `validation is None` raises `SnapshotPromotionError`: FR-034's "MUST NOT promote
    an unvalidated snapshot" is enforced here, at the one place both are read together.
    """
    data = _load_toml(snapshot_toml_text)
    table = _require_table(data, "snapshot")
    promoted = table.get("promoted", False)
    if not isinstance(promoted, bool):
        raise SnapshotError(
            f"snapshot.toml: [snapshot].promoted must be a boolean, got {promoted!r}"
        )
    validation_table = data.get("validation")
    validation: ValidationRecord | None
    if validation_table is None or (isinstance(validation_table, dict) and not validation_table):
        validation = None
    elif not isinstance(validation_table, dict):
        raise SnapshotError("snapshot.toml: [validation] must be a table")
    else:
        validation = _parse_validation_record(validation_table)
        if validation.method == "carry-forward":
            describes_build = table.get("describes_build")
            if not isinstance(describes_build, int) or isinstance(describes_build, bool):
                raise SnapshotError(
                    "snapshot.toml: [snapshot].describes_build must be an integer before a "
                    "carry-forward [validation] record can be checked for completeness"
                )
            _check_carry_forward_completeness(validation, describes_build)
    if promoted and validation is None:
        raise SnapshotPromotionError(
            "snapshot.toml: promoted = true requires a non-empty [validation] record (FR-034); "
            "an unvalidated snapshot is never promoted"
        )
    return promoted, validation


def load_snapshot(directory: str) -> Snapshot:
    """Load one packaged snapshot by its directory name under `snapshots/`.

    Recomputes the digest over the packaged `rules.json` and `effects.toml` and compares it with
    the digest `snapshot.toml` records; a disagreement raises `SnapshotDigestMismatch` instead of
    returning anything — there is no code path that serves stale or tampered content (FR-025). The
    digest is checked before promotion is read: a tampered snapshot is refused on that basis alone,
    regardless of what its `promoted`/`[validation]` fields claim. Once the digest matches,
    `parse_promotion` is applied and may itself raise `SnapshotPromotionError` (FR-034) — loading
    an unpromoted, unvalidated snapshot is not an error; it is only excluded from
    `load_resolvable_snapshots`.
    """
    snapshot_dir = _snapshots_root().joinpath(directory)
    if not snapshot_dir.is_dir():
        raise SnapshotError(f"no packaged snapshot directory {directory!r}")
    identity_text = snapshot_dir.joinpath(IDENTITY_FILENAME).read_text(encoding="utf-8")
    identity = parse_identity(identity_text)
    rules_json = snapshot_dir.joinpath("rules.json").read_bytes()
    effects_toml = snapshot_dir.joinpath("effects.toml").read_bytes()
    recomputed = compute_digest(rules_json, effects_toml)
    if recomputed != identity.digest:
        raise SnapshotDigestMismatch(
            f"{directory}: recorded digest {identity.digest} does not match the digest "
            f"recomputed over rules.json and effects.toml, {recomputed}"
        )
    promoted, validation = parse_promotion(identity_text)
    return Snapshot(
        directory=directory, identity=identity, promoted=promoted, validation=validation
    )


def load_all_snapshots() -> tuple[Snapshot, ...]:
    """Every packaged snapshot, loaded and digest-verified, in directory-name order.

    Used by the immutability test that walks every committed snapshot directory — a snapshot that
    fails to load (a bad digest, a malformed identity, an unpromotable promotion flag) raises
    rather than being silently skipped. Includes unpromoted snapshots: they are valid, loadable
    data, just not resolvable by build (`load_resolvable_snapshots` is the filtered set).
    """
    return tuple(load_snapshot(name) for name in list_snapshot_directories())


def load_resolvable_snapshots() -> tuple[Snapshot, ...]:
    """Every packaged snapshot that is **promoted** — the set FR-034's "only a promoted snapshot
    is resolvable by build" describes, and the set `snapshot_for(build)` resolves against.

    An unpromoted snapshot loads without error through `load_all_snapshots` (it is not corrupt,
    merely not yet validated) but never appears here: promotion, not mere presence on disk, is
    what makes a snapshot answerable.
    """
    return tuple(snapshot for snapshot in load_all_snapshots() if snapshot.promoted)


@dataclass(frozen=True, slots=True)
class NoSnapshotForBuild:
    """`snapshot_for(build)` found no promoted snapshot describing `build` (FR-027).

    This is an **interim** gap value, not the full `KnowledgeGap` FR-035 to FR-037 describe (entity,
    field, affected civilisation, what it prevents, a computed severity) — see this module's
    docstring, "Build resolution (FR-027, T641)". `cause` is fixed to the literal
    contracts/knowledge-base.md, "Resolution by build" names, `"no-snapshot-for-build"`; it is
    still a field, not a bare string return, so a caller pattern-matching on this type does not
    need to know the literal to detect "this is a gap, and this is which one".

    **For T647**: fold this into `gaps.py`'s `KnowledgeGap` rather than leaving it as a second,
    parallel gap vocabulary — `build` is the one fact this call site has to offer.
    """

    build: int
    cause: str = "no-snapshot-for-build"


def snapshot_for(build: int) -> Snapshot | NoSnapshotForBuild:
    """FR-027's build resolution: an exact match on `describes_build` among
    `load_resolvable_snapshots()`, or a gap.

    Exactly one parameter, no more: there is no nearest, no latest and no fallback parameter,
    because an argument that exists will eventually be passed
    (`test_snapshot_for_accepts_exactly_one_required_parameter` asserts this structurally, not
    only by review). A recording from a build with no promoted snapshot is
    `NoSnapshotForBuild(build)`, never the nearest promoted snapshot and never the unpromoted
    snapshot that happens to share the same `describes_build` — promotion still gates
    resolvability (contracts/knowledge-base.md, "Promotion").

    More than one promoted snapshot claiming the same `describes_build` is not a gap and not
    silently resolved by picking one: it is a data-integrity violation this module has no business
    papering over, so it raises `SnapshotError` instead. Nothing upstream of promotion (T639) or
    carry-forward (T642) currently prevents two promoted snapshots from describing the same build,
    so this is checked here, at the one place both would be read together.
    """
    matches = tuple(
        snapshot
        for snapshot in load_resolvable_snapshots()
        if snapshot.identity.describes_build == build
    )
    if not matches:
        return NoSnapshotForBuild(build=build)
    if len(matches) > 1:
        raise SnapshotError(
            f"more than one promoted snapshot describes build {build}: "
            f"{[snapshot.directory for snapshot in matches]}"
        )
    return matches[0]
