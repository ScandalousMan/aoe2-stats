"""FR-024's identity and digest, FR-025's "never modified" (T638); FR-034's promotion sequence and
FR-030's validation record (T639).

contracts/knowledge-base.md, "Identity and immutability": identity is `source`, `source_version`,
`describes_build`, `digest`; the digest is recomputed on load over `rules.json` and `effects.toml`,
and a mismatch refuses to load. A test walks every committed snapshot directory and fails if any
file's digest differs from its recorded one — that is `test_every_committed_snapshot_verifies` at
the bottom of this file, run against the real packaged `packages/knowledge/snapshots/` tree through
`importlib.resources`, exactly as production code reads it. Every other test here uses a synthetic
snapshot directory (`_write_snapshot_dir`) and monkeypatches `_snapshots_root`, so the loader's
refusals can be planted and proven without touching (or, worse, needing to un-verify) real,
committed content.

contracts/knowledge-base.md, "Promotion": `promoted = true` is refused unless `[validation]` is a
non-empty table; an unpromoted snapshot loads fine as data but is excluded from
`load_resolvable_snapshots`, the set `snapshot_for(build)` resolves against. Two committed
fixtures exercise this end to end without monkeypatching: `aoe2techtree-test-stub` (unpromoted) and
`aoe2techtree-180059` (promoted, with a real validation record).

contracts/knowledge-base.md, "Resolution by build" (T641, FR-027): `snapshot_for(build)` is an
exact match on `describes_build` among `load_resolvable_snapshots()`, or a
`gaps.KnowledgeGap(cause="no-snapshot-for-build")` (T647) — no nearest, no latest, no fallback
parameter.
`test_snapshot_for_accepts_exactly_one_required_parameter` makes that a structural property of the
signature, not a habit a future edit could quietly break.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.gaps import KnowledgeGap
from aoe2stats_knowledge.snapshot import (
    Snapshot,
    SnapshotCarryForwardIncomplete,
    SnapshotDigestMismatch,
    SnapshotError,
    SnapshotIdentity,
    SnapshotPromotionError,
    ValidationRecord,
    compute_digest,
    list_snapshot_directories,
    load_all_snapshots,
    load_resolvable_snapshots,
    load_snapshot,
    parse_identity,
    parse_promotion,
    snapshot_for,
)

_RULES_JSON = b'{"entities": {}}'
_EFFECTS_TOML = b"# no effects yet\n"

#: Sentinel distinct from `None`, which means "omit this field from the TOML entirely" — used by
#: `_identity_toml`'s `digest` parameter, where `None` is also a meaningful value to pass through
#: (the default keeps computing the real digest of `_RULES_JSON`/`_EFFECTS_TOML`).
_DEFAULT_DIGEST = object()


def _quoted_digest(digest: str) -> str:
    """A raw digest string (`sha256:...` or a deliberately malformed one) as a quoted TOML value."""
    return digest if digest.startswith('"') else f'"{digest}"'


def _identity_toml(
    *,
    source: str | None = '"aoe2techtree"',
    source_version: str | None = '"deadbeef"',
    describes_build: str | None = "0",
    digest: str | object | None = _DEFAULT_DIGEST,
    extra: str = "",
) -> str:
    """Build `snapshot.toml` text. Any of `source`, `source_version`, `describes_build`, `digest`
    passed as `None` is **omitted** from the `[snapshot]` table, to test a missing field; a TOML
    value must be passed already quoted/formatted (e.g. `'"a"'`, `"1"`), except `digest`, which may
    be passed as a bare (unquoted) string and is quoted here for convenience."""
    resolved_digest = (
        f'"{compute_digest(_RULES_JSON, _EFFECTS_TOML)}"'
        if digest is _DEFAULT_DIGEST
        else (None if digest is None else _quoted_digest(digest))  # type: ignore[arg-type]
    )
    lines = ["[snapshot]"]
    if source is not None:
        lines.append(f"source = {source}")
    if source_version is not None:
        lines.append(f"source_version = {source_version}")
    if describes_build is not None:
        lines.append(f"describes_build = {describes_build}")
    if resolved_digest is not None:
        lines.append(f"digest = {resolved_digest}")
    lines.append(extra)
    return "\n".join(lines) + "\n"


def _validation_toml(
    *,
    method: str | None = '"second-source"',
    checked_against: str | None = '"the game client, directly"',
    performed_by: str | None = '"a test author"',
    performed_at: str | None = '"2026-01-01"',
    extra: str = "",
) -> str:
    """A `[validation]` table's text. Any of the four FR-030 fields passed as `None` is omitted,
    to test a partial (malformed) validation record; a TOML value must be passed already quoted
    (e.g. `'"a"'`), mirroring `_identity_toml`'s convention. `method` defaults to a generic,
    non-`"carry-forward"` placeholder on purpose: `"carry-forward"` now carries T642's own
    completeness invariant (`_check_carry_forward_completeness`), so a test that only wants a
    generic, method-agnostic validation record must not spell that string by accident."""
    lines = ["[validation]"]
    if method is not None:
        lines.append(f"method = {method}")
    if checked_against is not None:
        lines.append(f"checked_against = {checked_against}")
    if performed_by is not None:
        lines.append(f"performed_by = {performed_by}")
    if performed_at is not None:
        lines.append(f"performed_at = {performed_at}")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _write_snapshot_dir(
    root: Path,
    name: str,
    *,
    rules_json: bytes = _RULES_JSON,
    effects_toml: bytes = _EFFECTS_TOML,
    snapshot_toml: str | None = None,
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "rules.json").write_bytes(rules_json)
    (directory / "effects.toml").write_bytes(effects_toml)
    (directory / "disagreements.toml").write_text("# none\n", encoding="utf-8")
    (directory / "snapshot.toml").write_text(
        snapshot_toml if snapshot_toml is not None else _identity_toml(), encoding="utf-8"
    )
    return directory


# --------------------------------------------------------------------------------- compute_digest


def test_compute_digest_is_deterministic() -> None:
    assert compute_digest(_RULES_JSON, _EFFECTS_TOML) == compute_digest(_RULES_JSON, _EFFECTS_TOML)


def test_compute_digest_is_a_sha256_prefixed_hex_string() -> None:
    digest = compute_digest(_RULES_JSON, _EFFECTS_TOML)
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    int(digest.removeprefix("sha256:"), 16)  # raises ValueError if not hex


def test_compute_digest_changes_when_rules_json_changes() -> None:
    changed = compute_digest(b'{"entities": {"x": 1}}', _EFFECTS_TOML)
    assert changed != compute_digest(_RULES_JSON, _EFFECTS_TOML)


def test_compute_digest_changes_when_effects_toml_changes() -> None:
    changed = compute_digest(_RULES_JSON, b"# a bonus now exists\n")
    assert changed != compute_digest(_RULES_JSON, _EFFECTS_TOML)


def test_compute_digest_does_not_confuse_the_two_files_shuffled() -> None:
    """Swapping which file holds which bytes must not produce the same digest — the filename and
    length prefix (not merely concatenation) is what rules this out."""
    a, b = b"one", b"two-longer"
    assert compute_digest(a, b) != compute_digest(b, a)


# ---------------------------------------------------------------------------------- parse_identity


def test_parse_identity_reads_the_fr024_fields() -> None:
    digest = compute_digest(_RULES_JSON, _EFFECTS_TOML)
    text = _identity_toml(
        source='"aoe2techtree"',
        source_version='"b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0"',
        describes_build="101102",
        digest=digest,
    )
    identity = parse_identity(text)
    assert identity == SnapshotIdentity(
        source="aoe2techtree",
        source_version="b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0",
        describes_build=101102,
        digest=digest,
    )


def test_parse_identity_ignores_fields_outside_fr024() -> None:
    """`promoted`, `civilisations_modelled` and a validation table are T639's; a snapshot.toml
    carrying them is not malformed from this task's point of view."""
    text = _identity_toml(extra="promoted = false\ncivilisations_modelled = []\n")
    parse_identity(text)  # does not raise


def test_parse_identity_rejects_malformed_toml() -> None:
    with pytest.raises(SnapshotError, match="not valid TOML"):
        parse_identity("[snapshot\nsource = broken")


def test_parse_identity_rejects_missing_snapshot_table() -> None:
    with pytest.raises(SnapshotError, match=r"\[snapshot\]"):
        parse_identity("other = 1\n")


@pytest.mark.parametrize("field", ["source", "source_version", "digest"])
def test_parse_identity_rejects_missing_string_field(field: str) -> None:
    """Only `field` is omitted; every other required field is present and valid, so a failure to
    match `field` in the raised message would show this test is catching the wrong thing."""
    with pytest.raises(SnapshotError, match=field):
        parse_identity(_identity_toml(**{field: None}))


def test_parse_identity_rejects_blank_source() -> None:
    with pytest.raises(SnapshotError, match="source"):
        parse_identity(_identity_toml(source='"   "'))


def test_parse_identity_rejects_missing_describes_build() -> None:
    with pytest.raises(SnapshotError, match="describes_build"):
        parse_identity(_identity_toml(describes_build=None))


def test_parse_identity_rejects_describes_build_as_string() -> None:
    with pytest.raises(SnapshotError, match="describes_build"):
        parse_identity(_identity_toml(describes_build='"101102"'))


def test_parse_identity_rejects_describes_build_as_bool() -> None:
    """`bool` is a subclass of `int` in Python; a TOML `true`/`false` must not silently pass as a
    build number."""
    with pytest.raises(SnapshotError, match="describes_build"):
        parse_identity(_identity_toml(describes_build="true"))


def test_parse_identity_rejects_digest_with_no_sha256_prefix() -> None:
    with pytest.raises(SnapshotError, match="sha256"):
        parse_identity(_identity_toml(digest="deadbeef"))


def test_parse_identity_rejects_digest_of_the_wrong_length() -> None:
    with pytest.raises(SnapshotError, match="sha256"):
        parse_identity(_identity_toml(digest="sha256:abc"))


# -------------------------------------------------------------------------------- parse_promotion


def test_parse_promotion_defaults_to_unpromoted_with_no_validation() -> None:
    """No `promoted` key and no `[validation]` table at all: the most common shape for a snapshot
    that has not gone through FR-034's sequence yet."""
    promoted, validation = parse_promotion(_identity_toml())
    assert promoted is False
    assert validation is None


def test_parse_promotion_reads_a_promoted_snapshot_with_its_validation_record() -> None:
    text = _identity_toml(
        extra="promoted = true\n\n"
        + _validation_toml(
            method='"game-comparison"',
            checked_against='"the game client, directly"',
            performed_by='"a test author"',
            performed_at='"2026-01-01"',
        )
    )
    promoted, validation = parse_promotion(text)
    assert promoted is True
    assert validation == ValidationRecord(
        method="game-comparison",
        checked_against="the game client, directly",
        performed_by="a test author",
        performed_at="2026-01-01",
        details={},
    )


def test_parse_promotion_reads_an_unset_validation_record_alongside_an_unpromoted_snapshot() -> (
    None
):
    """A validation record may exist before promotion (FR-034's sequence records validation, then
    promotes) — `promoted = false` with a full `[validation]` table is not itself an error."""
    text = _identity_toml(extra="promoted = false\n\n" + _validation_toml())
    promoted, validation = parse_promotion(text)
    assert promoted is False
    assert validation is not None
    assert validation.method == "second-source"


def test_parse_promotion_keeps_extra_validation_keys_in_details() -> None:
    """`details` is the extension point T642 adds carry-forward's per-build note list into — any
    key beyond the four FR-030 fields is kept, not dropped."""
    text = _identity_toml(
        extra="promoted = true\n\n"
        + _validation_toml(extra="builds_confirmed_unchanged = [101101, 101102]")
    )
    _, validation = parse_promotion(text)
    assert validation is not None
    assert validation.details == {"builds_confirmed_unchanged": [101101, 101102]}


def test_parse_promotion_raises_when_promoted_is_not_a_bool() -> None:
    with pytest.raises(SnapshotError, match="promoted"):
        parse_promotion(_identity_toml(extra='promoted = "true"'))


@pytest.mark.parametrize(
    "field",
    ["method", "checked_against", "performed_by", "performed_at"],
)
def test_parse_promotion_raises_when_validation_is_missing_a_required_field(field: str) -> None:
    """A `[validation]` table missing one of the four FR-030 fields is malformed, not merely
    incomplete — raised regardless of `promoted`, so a half-written validation record is never
    mistaken for "no validation recorded"."""
    text = _identity_toml(
        extra="promoted = false\n\n" + _validation_toml(**{field: None})  # type: ignore[arg-type]
    )
    with pytest.raises(SnapshotError, match=field):
        parse_promotion(text)


def test_parse_promotion_rejects_a_blank_validation_field() -> None:
    text = _identity_toml(extra="promoted = false\n\n" + _validation_toml(method='"   "'))
    with pytest.raises(SnapshotError, match="method"):
        parse_promotion(text)


def test_parse_promotion_raises_when_validation_is_not_a_table() -> None:
    """`validation = 1` must be a **root**-level key, not nested inside `[snapshot]` — TOML has no
    way to reopen the root table once `[snapshot]` starts, so it is prepended here instead of
    passed through `_identity_toml`'s `extra`."""
    text = "validation = 1\n\n" + _identity_toml(extra="promoted = false")
    with pytest.raises(SnapshotError, match="validation"):
        parse_promotion(text)


# ------------------------------------------ carry-forward completeness (T642, research.md D4)


def _carry_forward_entry(build: int) -> str:
    """One `[[validation.carry_forward.builds]]` table, all four D4 fields present and non-blank,
    for a synthetic `build`."""
    return (
        "[[validation.carry_forward.builds]]\n"
        f"build = {build}\n"
        f'notes_consulted = "patch notes for build {build}"\n'
        f'read_at = "https://example.test/patch-notes/{build}"\n'
        'date_read = "2026-01-01"\n'
        'reading = "no field this pack carries changed"\n'
    )


def _carry_forward_toml(
    *,
    describes_build: int = 105,
    source_last_implemented_build: int = 100,
    intervening_builds: str = "[102, 105]",
    entries: str,
) -> str:
    """A complete `snapshot.toml`, `promoted = true`, `method = "carry-forward"`, with the given
    `[validation.carry_forward]` declarations and `entries` as the `[[...builds]]` tables text."""
    return _identity_toml(
        describes_build=str(describes_build),
        extra=(
            "promoted = true\n\n"
            + _validation_toml(method='"carry-forward"')
            + "\n\n[validation.carry_forward]\n"
            f"source_last_implemented_build = {source_last_implemented_build}\n"
            f"intervening_builds = {intervening_builds}\n\n" + entries
        ),
    )


def test_parse_promotion_accepts_a_complete_carry_forward_record() -> None:
    """(a) every intervening build (102 and the target, 105) is attested: promotes cleanly and the
    per-build detail survives into `ValidationRecord.details`."""
    text = _carry_forward_toml(
        entries=_carry_forward_entry(102) + "\n" + _carry_forward_entry(105),
    )
    promoted, validation = parse_promotion(text)
    assert promoted is True
    assert validation is not None
    carry_forward = validation.details["carry_forward"]
    assert carry_forward["intervening_builds"] == [102, 105]
    assert {entry["build"] for entry in carry_forward["builds"]} == {102, 105}


def test_parse_promotion_raises_when_a_carry_forward_record_is_missing_one_intervening_build() -> (
    None
):
    """(b) 105 (the target build itself) is declared in `intervening_builds` but never attested in
    `builds` — refused, naming the missing build, not silently accepted as "close enough"."""
    text = _carry_forward_toml(entries=_carry_forward_entry(102))
    with pytest.raises(SnapshotCarryForwardIncomplete, match=r"\b105\b"):
        parse_promotion(text)


def test_parse_promotion_raises_when_a_carry_forward_build_entry_is_missing_a_required_field() -> (
    None
):
    """A `builds` entry for a declared build with a blank `reading` is not "attested, just
    incomplete" — it is the same refusal as an entry that is entirely absent."""
    incomplete_entry = (
        "[[validation.carry_forward.builds]]\n"
        "build = 105\n"
        'notes_consulted = "patch notes for build 105"\n'
        'read_at = "https://example.test/patch-notes/105"\n'
        'date_read = "2026-01-01"\n'
        'reading = "   "\n'
    )
    text = _carry_forward_toml(entries=_carry_forward_entry(102) + "\n" + incomplete_entry)
    with pytest.raises(SnapshotCarryForwardIncomplete, match="reading"):
        parse_promotion(text)


def test_parse_promotion_raises_when_carry_forward_attests_a_build_not_declared() -> None:
    """The inverse gap: an attestation exists for build 999, which `intervening_builds` never
    named as needing coverage — proves nothing about completeness, so it is refused too."""
    text = _carry_forward_toml(
        entries=(
            _carry_forward_entry(102)
            + "\n"
            + _carry_forward_entry(105)
            + "\n"
            + _carry_forward_entry(999)
        ),
    )
    with pytest.raises(SnapshotError, match=r"\b999\b"):
        parse_promotion(text)


def test_parse_promotion_raises_when_carry_forward_has_no_carry_forward_table() -> None:
    """`method = "carry-forward"` with no `[validation.carry_forward]` table at all is the same
    "no attestation" refusal as one missing a specific build."""
    text = _identity_toml(extra="promoted = true\n\n" + _validation_toml(method='"carry-forward"'))
    with pytest.raises(SnapshotCarryForwardIncomplete, match="carry_forward"):
        parse_promotion(text)


def test_parse_promotion_raises_when_intervening_builds_does_not_end_at_describes_build() -> None:
    text = _carry_forward_toml(
        describes_build=105,
        intervening_builds="[102, 104]",
        entries=_carry_forward_entry(102) + "\n" + _carry_forward_entry(104),
    )
    with pytest.raises(SnapshotError, match="describes_build"):
        parse_promotion(text)


def test_parse_promotion_does_not_check_carry_forward_completeness_for_another_method() -> None:
    """A `[validation.carry_forward]`-shaped invariant is specific to `method = "carry-forward"` —
    a `"second-source"` validation with no such table at all is unaffected by this task."""
    text = _identity_toml(extra="promoted = true\n\n" + _validation_toml(method='"second-source"'))
    promoted, validation = parse_promotion(text)
    assert promoted is True
    assert validation is not None
    assert validation.details == {}


# ---------------------------------------------- promoted = true with no validation record (FR-034)


def test_parse_promotion_refuses_promoted_true_with_no_validation_table_at_all() -> None:
    """The hard invariant this task exists for: FR-034 forbids promoting an unvalidated snapshot,
    and there is no `[validation]` table here at all."""
    with pytest.raises(SnapshotPromotionError, match="validation"):
        parse_promotion(_identity_toml(extra="promoted = true"))


def test_parse_promotion_refuses_promoted_true_with_an_empty_validation_table() -> None:
    """The twin case: a `[validation]` table is present but carries no keys — also "no validation
    recorded", not a record with blank fields, and refused the same way."""
    with pytest.raises(SnapshotPromotionError, match="validation"):
        parse_promotion(_identity_toml(extra="promoted = true\n\n[validation]"))


# ---------------------------------------------------------------------------------- load_snapshot


def test_load_snapshot_returns_a_snapshot_when_the_digest_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_snapshot_dir(tmp_path, "good")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    result = load_snapshot("good")
    assert isinstance(result, Snapshot)
    assert result.directory == "good"
    assert result.identity.digest == compute_digest(_RULES_JSON, _EFFECTS_TOML)


def test_load_snapshot_defaults_to_unpromoted_with_no_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A snapshot with no `promoted`/`[validation]` fields at all loads fine as data (T638's
    identity mechanism does not require them) — `promoted` and `validation` are `False`/`None`,
    the dataclass defaults, distinct from an explicit `promoted = false`."""
    _write_snapshot_dir(tmp_path, "unvalidated")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    result = load_snapshot("unvalidated")
    assert result.promoted is False
    assert result.validation is None


def test_load_snapshot_returns_a_promoted_snapshot_with_its_validation_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) promoted + valid works end to end: a snapshot with `promoted = true` and a full
    `[validation]` table loads without error and carries both on the returned `Snapshot`."""
    snapshot_toml = _identity_toml(
        extra="promoted = true\n\n" + _validation_toml(method='"game-comparison"')
    )
    _write_snapshot_dir(tmp_path, "promoted", snapshot_toml=snapshot_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    result = load_snapshot("promoted")
    assert result.promoted is True
    assert result.validation is not None
    assert result.validation.method == "game-comparison"


def test_load_snapshot_raises_promotion_error_when_promoted_true_with_no_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) promoted + empty validation is refused, at `load_snapshot` itself, not only at
    `parse_promotion` in isolation — the digest matches here, so the only reason to refuse is the
    promotion invariant."""
    snapshot_toml = _identity_toml(extra="promoted = true")
    _write_snapshot_dir(tmp_path, "unvalidated-promotion", snapshot_toml=snapshot_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotPromotionError):
        load_snapshot("unvalidated-promotion")


def test_load_snapshot_raises_promotion_error_when_promoted_true_with_an_empty_validation_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_toml = _identity_toml(extra="promoted = true\n\n[validation]")
    _write_snapshot_dir(tmp_path, "empty-validation", snapshot_toml=snapshot_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotPromotionError):
        load_snapshot("empty-validation")


def test_load_snapshot_raises_when_rules_json_is_tampered_after_the_digest_was_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest recorded in snapshot.toml is over the *original* rules.json; a tampered file on
    disk must refuse to load rather than silently serving the new bytes under the old identity."""
    _write_snapshot_dir(tmp_path, "tampered")
    (tmp_path / "tampered" / "rules.json").write_bytes(b'{"entities": {"new": 1}}')
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotDigestMismatch, match="tampered"):
        load_snapshot("tampered")


def test_load_snapshot_raises_when_effects_toml_is_tampered_after_the_digest_was_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The twin of the rules.json case: effects.toml is the other half of the digested content,
    and a change there alone must be caught too, not only a change to rules.json."""
    _write_snapshot_dir(tmp_path, "tampered")
    (tmp_path / "tampered" / "effects.toml").write_text("# a new bonus\n", encoding="utf-8")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotDigestMismatch, match="tampered"):
        load_snapshot("tampered")


def test_load_snapshot_raises_when_snapshot_toml_records_a_digest_that_never_matched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_digest = compute_digest(b"not", b"the real content")
    _write_snapshot_dir(tmp_path, "wrong", snapshot_toml=_identity_toml(digest=bad_digest))
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotDigestMismatch):
        load_snapshot("wrong")


def test_load_snapshot_raises_for_a_directory_that_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotError, match="absent"):
        load_snapshot("absent")


# ---------------------------------------------------------------------- list_snapshot_directories


def test_list_snapshot_directories_is_empty_when_the_root_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path / "absent")
    assert list_snapshot_directories() == ()


def test_list_snapshot_directories_is_sorted_and_ignores_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_snapshot_dir(tmp_path, "zebra")
    _write_snapshot_dir(tmp_path, "alpha")
    (tmp_path / "README.md").write_text("not a snapshot", encoding="utf-8")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    assert list_snapshot_directories() == ("alpha", "zebra")


def test_load_all_snapshots_loads_every_listed_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_snapshot_dir(tmp_path, "one")
    _write_snapshot_dir(tmp_path, "two")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    loaded = load_all_snapshots()
    assert [s.directory for s in loaded] == ["one", "two"]


def test_load_all_snapshots_raises_if_any_one_snapshot_fails_its_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch load is not partial: one bad snapshot must fail the whole call, never a silently
    shorter result."""
    _write_snapshot_dir(tmp_path, "one")
    _write_snapshot_dir(tmp_path, "two")
    (tmp_path / "two" / "rules.json").write_bytes(b'{"entities": {"tampered": true}}')
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    with pytest.raises(SnapshotDigestMismatch, match="two"):
        load_all_snapshots()


# --------------------------------------------------------------------- load_resolvable_snapshots


def test_load_resolvable_snapshots_is_empty_when_nothing_is_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_snapshot_dir(tmp_path, "one")
    _write_snapshot_dir(tmp_path, "two")
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    assert load_resolvable_snapshots() == ()


def test_load_resolvable_snapshots_excludes_an_unpromoted_but_otherwise_valid_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) unpromoted loads but is excluded from resolution: a distinct concept from T638's
    digest-mismatch refusal — this snapshot is not corrupt, not tampered, and loads through
    `load_all_snapshots` without error; it is simply not promoted, and that alone excludes it."""
    _write_snapshot_dir(tmp_path, "unpromoted")
    promoted_toml = _identity_toml(
        describes_build="1", extra="promoted = true\n\n" + _validation_toml()
    )
    _write_snapshot_dir(tmp_path, "promoted", snapshot_toml=promoted_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)

    all_snapshots = load_all_snapshots()
    assert [s.directory for s in all_snapshots] == ["promoted", "unpromoted"]

    resolvable = load_resolvable_snapshots()
    assert [s.directory for s in resolvable] == ["promoted"]
    assert all(s.promoted for s in resolvable)


# ------------------------------------------------ the real, committed packaged tree (no patching)


def test_every_committed_snapshot_verifies_against_its_own_recorded_digest() -> None:
    """FR-025's "never modified or removed" is asserted, not merely requested: every snapshot
    directory actually committed under `packages/knowledge/snapshots/` is loaded here through the
    real, unpatched `importlib.resources` path production code uses, and `load_snapshot` raises
    `SnapshotDigestMismatch` the moment any file disagrees with its recorded digest. At least one
    snapshot must be committed, or this test would pass on an empty tree without proving anything.
    """
    directories = list_snapshot_directories()
    assert directories, "no committed snapshot directory found under packages/knowledge/snapshots/"
    snapshots = load_all_snapshots()
    assert [s.directory for s in snapshots] == list(directories)
    for loaded in snapshots:
        rules_json = (
            snapshot_module._snapshots_root().joinpath(loaded.directory).joinpath("rules.json")
        )
        effects_toml = (
            snapshot_module._snapshots_root().joinpath(loaded.directory).joinpath("effects.toml")
        )
        recomputed = compute_digest(rules_json.read_bytes(), effects_toml.read_bytes())
        assert recomputed == loaded.identity.digest, (
            f"{loaded.directory}: committed rules.json/effects.toml no longer matches the digest "
            "recorded in snapshot.toml"
        )


def test_the_committed_unpromoted_fixture_loads_but_is_not_resolvable() -> None:
    """`aoe2techtree-test-stub` is committed deliberately unpromoted (its own `snapshot.toml` says
    so) — proving on the real, unpatched tree that an unpromoted snapshot is valid, loadable data
    that is nonetheless absent from the resolvable set."""
    unpromoted = load_snapshot("aoe2techtree-test-stub")
    assert unpromoted.promoted is False
    assert unpromoted.validation is None
    resolvable_directories = {snapshot.directory for snapshot in load_resolvable_snapshots()}
    assert "aoe2techtree-test-stub" not in resolvable_directories


def test_the_committed_promoted_fixture_is_promoted_and_resolvable() -> None:
    """`aoe2techtree-180059` is committed promoted, with a real, non-empty validation
    record — proving the promotion mechanism end to end against real, unpatched, committed
    content rather than only a synthetic `tmp_path` directory."""
    promoted = load_snapshot("aoe2techtree-180059")
    assert promoted.promoted is True
    assert promoted.validation is not None
    assert promoted.validation.method
    assert promoted.validation.checked_against
    assert promoted.validation.performed_by
    assert promoted.validation.performed_at
    resolvable_directories = {snapshot.directory for snapshot in load_resolvable_snapshots()}
    assert "aoe2techtree-180059" in resolvable_directories


# --------------------------------------------------------------------------------- snapshot_for


def test_snapshot_for_accepts_exactly_one_required_parameter() -> None:
    """FR-027: "no nearest, no latest and no fallback parameter — the function must not accept
    one, because an argument that exists will be passed." Asserted structurally so a later edit
    that adds a `strategy=`/`allow_nearest=`/default-snapshot parameter fails this test loudly,
    rather than silently reintroducing the substitution FR-027 and FR-038 forbid."""
    parameters = list(inspect.signature(snapshot_for).parameters.values())
    assert len(parameters) == 1, f"snapshot_for must take exactly one parameter, got {parameters}"
    (build_parameter,) = parameters
    assert build_parameter.name == "build"
    assert build_parameter.default is inspect.Parameter.empty, (
        "snapshot_for's build parameter must be required, not defaulted — a default is itself a "
        "fallback"
    )
    assert build_parameter.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_snapshot_for_returns_the_promoted_snapshot_describing_the_exact_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    promoted_toml = _identity_toml(
        describes_build="101102", extra="promoted = true\n\n" + _validation_toml()
    )
    _write_snapshot_dir(tmp_path, "promoted", snapshot_toml=promoted_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)

    result = snapshot_for(101102)

    assert isinstance(result, Snapshot)
    assert result.directory == "promoted"
    assert result.identity.describes_build == 101102


def test_snapshot_for_returns_a_gap_when_no_promoted_snapshot_describes_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    promoted_toml = _identity_toml(
        describes_build="101102", extra="promoted = true\n\n" + _validation_toml()
    )
    _write_snapshot_dir(tmp_path, "promoted", snapshot_toml=promoted_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)

    result = snapshot_for(999999)

    assert result == KnowledgeGap(cause="no-snapshot-for-build", build=999999)
    assert result.cause == "no-snapshot-for-build"


def test_snapshot_for_returns_a_gap_when_only_an_unpromoted_snapshot_describes_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Promotion still gates resolvability: an unpromoted snapshot whose `describes_build`
    matches the requested build is never returned — the caller receives the gap, not the
    unvalidated snapshot, exactly as it would if no snapshot at all described that build."""
    unpromoted_toml = _identity_toml(describes_build="101102")
    _write_snapshot_dir(tmp_path, "unpromoted", snapshot_toml=unpromoted_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)

    result = snapshot_for(101102)

    assert result == KnowledgeGap(cause="no-snapshot-for-build", build=101102)


def test_snapshot_for_raises_when_two_promoted_snapshots_describe_the_same_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two promoted snapshots claiming the same `describes_build` is a data-integrity violation,
    not a normal case with a value to silently pick from — it is not a gap either, since a gap
    means "no promoted snapshot describes this build", the opposite of what happened here."""
    first_rules = b'{"entities": {"first": 1}}'
    second_rules = b'{"entities": {"second": 1}}'
    first_toml = _identity_toml(
        describes_build="101102",
        digest=compute_digest(first_rules, _EFFECTS_TOML),
        extra="promoted = true\n\n" + _validation_toml(),
    )
    second_toml = _identity_toml(
        describes_build="101102",
        digest=compute_digest(second_rules, _EFFECTS_TOML),
        extra="promoted = true\n\n" + _validation_toml(),
    )
    _write_snapshot_dir(tmp_path, "first", rules_json=first_rules, snapshot_toml=first_toml)
    _write_snapshot_dir(tmp_path, "second", rules_json=second_rules, snapshot_toml=second_toml)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)

    with pytest.raises(SnapshotError, match="more than one promoted snapshot"):
        snapshot_for(101102)


def test_snapshot_for_resolves_the_committed_promoted_fixture_by_its_real_build() -> None:
    """Against the real, unpatched, committed tree: `aoe2techtree-180059` now
    `describes_build = 180059`, the game build the committed reference recordings actually report
    (`tests/fixtures/replays/README.md`), wired there by T642's carry-forward validation record —
    resolving that exact build returns it."""
    result = snapshot_for(180059)
    assert isinstance(result, Snapshot)
    assert result.directory == "aoe2techtree-180059"


def test_the_committed_promoted_fixtures_validation_record_is_a_complete_carry_forward() -> None:
    """(c) "make it real": the committed fixture's own `[validation]` record is not a synthetic
    example — its `carry_forward` details name the real source revision's last-implemented build
    (177723, research.md D3's commit-message reading), the real intervening builds the committed
    recordings' build (180059) forced (research.md D4: "two further builds unimplemented in
    between" — 178524 and 179158), and a per-build attestation for all three, each carrying its
    weakest-link statement as data (research.md D4's "record ... in the validation record, not in
    a comment") rather than a placeholder string."""
    promoted = load_snapshot("aoe2techtree-180059")
    assert promoted.validation is not None
    assert promoted.validation.method == "carry-forward"
    carry_forward = promoted.validation.details["carry_forward"]
    assert carry_forward["source_last_implemented_build"] == 177723
    assert carry_forward["intervening_builds"] == [178524, 179158, 180059]
    assert carry_forward["weakest_link"]
    attested_builds = {entry["build"] for entry in carry_forward["builds"]}
    assert attested_builds == {178524, 179158, 180059}
    for entry in carry_forward["builds"]:
        for field_name in ("notes_consulted", "read_at", "date_read", "reading"):
            assert entry[field_name].strip(), (entry["build"], field_name)


def test_snapshot_for_returns_a_gap_for_the_committed_unpromoted_fixtures_build() -> None:
    """`aoe2techtree-test-stub` (unpromoted) `describes_build = 0` — resolving build 0 must return
    a gap, never the unpromoted snapshot: promotion gates resolvability even when the build
    matches exactly (contracts/knowledge-base.md, "Promotion")."""
    result = snapshot_for(0)
    assert result == KnowledgeGap(cause="no-snapshot-for-build", build=0)


def test_snapshot_for_returns_a_gap_for_a_clearly_absent_build() -> None:
    """No committed snapshot, promoted or not, describes this build."""
    result = snapshot_for(999_999_999)
    assert result == KnowledgeGap(cause="no-snapshot-for-build", build=999_999_999)
