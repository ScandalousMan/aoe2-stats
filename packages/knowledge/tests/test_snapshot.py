"""FR-024's identity and digest, FR-025's "never modified" (T638).

contracts/knowledge-base.md, "Identity and immutability": identity is `source`, `source_version`,
`describes_build`, `digest`; the digest is recomputed on load over `rules.json` and `effects.toml`,
and a mismatch refuses to load. A test walks every committed snapshot directory and fails if any
file's digest differs from its recorded one — that is `test_every_committed_snapshot_verifies` at
the bottom of this file, run against the real packaged `packages/knowledge/snapshots/` tree through
`importlib.resources`, exactly as production code reads it. Every other test here uses a synthetic
snapshot directory (`_write_snapshot_dir`) and monkeypatches `_snapshots_root`, so the loader's
refusals can be planted and proven without touching (or, worse, needing to un-verify) real,
committed content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.snapshot import (
    Snapshot,
    SnapshotDigestMismatch,
    SnapshotError,
    SnapshotIdentity,
    compute_digest,
    list_snapshot_directories,
    load_all_snapshots,
    load_snapshot,
    parse_identity,
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
