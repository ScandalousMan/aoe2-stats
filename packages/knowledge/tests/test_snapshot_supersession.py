"""T746: a promoted snapshot is never edited (FR-025), so a correction ships as a second snapshot
that names the digest it supersedes.

contracts/knowledge-base.md, "Promotion" and "Resolution by build": resolution by build skips a
superseded snapshot, a superseded snapshot stays loadable by identity (SC-005), and the loader
refuses a `supersedes` that cannot be honoured - an unknown digest, a snapshot of another build, a
cycle, a snapshot superseded twice, an unpromoted superseder. Two promoted snapshots describing one
build with no `supersedes` between them still raise `SnapshotError`.

Every case here is a synthetic snapshot directory under `tmp_path` with `_snapshots_root`
monkeypatched, as `test_snapshot.py` does, and each refusal has a contrast case that loads. Nothing
here touches the committed tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.snapshot import (
    Snapshot,
    SnapshotError,
    compute_digest,
    load_all_snapshots,
    load_resolvable_snapshots,
    load_snapshot,
    pinned_snapshot,
    snapshot_for,
    verify_installed_snapshots,
)

_EFFECTS_TOML = b"# no effects yet\n"
_BUILD = 101_102
_VALIDATION = """
[validation]
method = "second-source"
checked_against = "a test"
performed_by = "a test author"
performed_at = "2026-01-01"
"""


def _rules(tag: str) -> bytes:
    return json.dumps({"entities": {}, "tag": tag}).encode("utf-8")


def _digest(tag: str) -> str:
    return compute_digest(_rules(tag), _EFFECTS_TOML)


def _write(
    root: Path,
    name: str,
    *,
    tag: str,
    build: int = _BUILD,
    promoted: bool = True,
    supersedes: str | None = None,
) -> str:
    """Write one snapshot directory and return its digest. `tag` makes the content, and so the
    digest, distinct per snapshot."""
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "rules.json").write_bytes(_rules(tag))
    (directory / "effects.toml").write_bytes(_EFFECTS_TOML)
    (directory / "disagreements.toml").write_text("# none\n", encoding="utf-8")
    lines = [
        "[snapshot]",
        'source = "aoe2techtree"',
        'source_version = "deadbeef"',
        f"describes_build = {build}",
        f'digest = "{_digest(tag)}"',
        f"promoted = {'true' if promoted else 'false'}",
    ]
    if supersedes is not None:
        lines.append(f'supersedes = "{supersedes}"')
    (directory / "snapshot.toml").write_text(
        "\n".join(lines) + "\n" + (_VALIDATION if promoted else ""), encoding="utf-8"
    )
    return _digest(tag)


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: tmp_path)
    return tmp_path


# ------------------------------------------------------------------ resolution skips a superseded


def test_resolution_by_build_skips_the_superseded_snapshot(root: Path) -> None:
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)

    resolved = snapshot_for(_BUILD)

    assert isinstance(resolved, Snapshot)
    assert resolved.directory == "second"
    assert resolved.supersedes == first
    verify_installed_snapshots()


def test_contrast_two_promoted_snapshots_of_one_build_without_supersedes_still_raise(
    root: Path,
) -> None:
    _write(root, "first", tag="first")
    _write(root, "second", tag="second")

    with pytest.raises(SnapshotError, match="more than one promoted snapshot"):
        snapshot_for(_BUILD)
    with pytest.raises(SnapshotError, match="more than one promoted snapshot"):
        verify_installed_snapshots()


def test_a_chain_resolves_to_its_last_link_only(root: Path) -> None:
    first = _write(root, "first", tag="first")
    second = _write(root, "second", tag="second", supersedes=first)
    _write(root, "third", tag="third", supersedes=second)

    resolved = snapshot_for(_BUILD)

    assert isinstance(resolved, Snapshot)
    assert resolved.directory == "third"
    assert {s.directory for s in load_all_snapshots()} == {"first", "second", "third"}


def test_supersession_is_per_build_and_leaves_other_builds_alone(root: Path) -> None:
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)
    _write(root, "other", tag="other", build=_BUILD + 1)

    other = snapshot_for(_BUILD + 1)
    assert isinstance(other, Snapshot)
    assert other.directory == "other"


# ------------------------------------------------------- a superseded snapshot stays loadable


def test_a_superseded_snapshot_stays_loadable_by_identity_and_by_pin(root: Path) -> None:
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)

    by_identity = [s for s in load_all_snapshots() if s.identity.digest == first]
    assert len(by_identity) == 1
    superseded = by_identity[0]
    assert superseded.directory == "first"
    assert superseded.promoted
    assert load_snapshot("first") == superseded

    with pinned_snapshot(superseded):
        assert snapshot_for(_BUILD) is superseded
    resolved = snapshot_for(_BUILD)
    assert isinstance(resolved, Snapshot)
    assert resolved.directory == "second"


def test_a_superseded_snapshot_is_not_in_the_current_set_but_is_in_the_promoted_set(
    root: Path,
) -> None:
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)

    assert {s.directory for s in load_resolvable_snapshots()} == {"first", "second"}
    assert {s.directory for s in snapshot_module.load_current_snapshots()} == {"second"}


def test_a_snapshot_that_supersedes_nothing_has_no_supersedes(root: Path) -> None:
    _write(root, "only", tag="only")

    only = load_snapshot("only")

    assert only.supersedes is None


# --------------------------------------------------------------------------- the loader refuses


def test_a_supersedes_naming_no_installed_snapshot_is_refused(root: Path) -> None:
    _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=_digest("nowhere"))

    with pytest.raises(SnapshotError, match="supersedes"):
        load_all_snapshots()


def test_a_supersedes_naming_a_snapshot_of_another_build_is_refused(root: Path) -> None:
    other_build = _write(root, "first", tag="first", build=_BUILD + 1)
    _write(root, "second", tag="second", supersedes=other_build)

    with pytest.raises(SnapshotError, match="same build"):
        load_all_snapshots()


def test_contrast_a_supersedes_naming_a_snapshot_of_the_same_build_loads(root: Path) -> None:
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)

    assert len(load_all_snapshots()) == 2


def test_a_supersedes_naming_an_unpromoted_snapshot_is_refused(root: Path) -> None:
    draft = _write(root, "draft", tag="draft", promoted=False)
    _write(root, "second", tag="second", supersedes=draft)

    with pytest.raises(SnapshotError, match="promoted"):
        load_all_snapshots()


def test_an_unpromoted_snapshot_may_not_supersede(root: Path) -> None:
    """An unpromoted snapshot never resolves, so letting it hide a promoted one would leave the
    build with no snapshot at all."""
    first = _write(root, "first", tag="first")
    _write(root, "draft", tag="draft", promoted=False, supersedes=first)

    with pytest.raises(SnapshotError, match="promoted"):
        load_all_snapshots()


def test_a_snapshot_may_not_supersede_itself(root: Path) -> None:
    _write(root, "first", tag="first", supersedes=_digest("first"))

    with pytest.raises(SnapshotError, match="cycle"):
        load_all_snapshots()


def test_a_cycle_of_two_is_refused(root: Path) -> None:
    _write(root, "first", tag="first", supersedes=_digest("second"))
    _write(root, "second", tag="second", supersedes=_digest("first"))

    with pytest.raises(SnapshotError, match="cycle"):
        load_all_snapshots()


def test_a_snapshot_superseded_twice_is_refused(root: Path) -> None:
    """Two snapshots superseding one would leave two live promoted snapshots for the build."""
    first = _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes=first)
    _write(root, "third", tag="third", supersedes=first)

    with pytest.raises(SnapshotError, match="superseded more than once"):
        load_all_snapshots()


def test_a_malformed_supersedes_is_refused(root: Path) -> None:
    _write(root, "first", tag="first")
    _write(root, "second", tag="second", supersedes="sha256:not-a-digest")

    with pytest.raises(SnapshotError, match="digest"):
        load_snapshot("second")


def test_a_supersedes_matching_two_installed_snapshots_is_refused(root: Path) -> None:
    """Two directories holding the same content have one digest; naming it names neither."""
    first = _write(root, "first", tag="first")
    _write(root, "copy-of-first", tag="first")
    _write(root, "second", tag="second", supersedes=first)

    with pytest.raises(SnapshotError, match="more than one"):
        load_all_snapshots()


def test_a_cycle_never_degrades_to_a_no_snapshot_gap(root: Path) -> None:
    """Every member of a cycle is superseded, so were it accepted the build would resolve to a
    `no-snapshot-for-build` gap while two promoted snapshots exist. It is refused instead."""
    _write(root, "first", tag="first", supersedes=_digest("second"))
    _write(root, "second", tag="second", supersedes=_digest("first"))

    with pytest.raises(SnapshotError, match="cycle"):
        snapshot_for(_BUILD)
