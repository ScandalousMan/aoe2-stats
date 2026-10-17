"""T709: `labels.label_in_snapshot` - a name looked up in the snapshot a document's digest names.

Real, packaged snapshots throughout (builds 180059 and 185872), never a stub: the question is what
the shipped tables say. The contrast cases are the ones FR-027 is about - a digest nothing has
must name nothing, even for a build that has a promoted snapshot.
"""

from __future__ import annotations

import pytest

from aoe2stats_knowledge import labels, snapshot

#: Ids no packaged snapshot names; `test_the_unnamed_ids_are_outside_every_snapshot` asserts it.
_UNNAMED_ID = "987654321"


def _digest(build: int) -> str:
    resolved = snapshot.snapshot_for(build)
    assert isinstance(resolved, snapshot.Snapshot)
    return resolved.identity.digest


@pytest.mark.parametrize("build", [180059, 185872])
def test_a_snapshots_own_digest_names_feudal_castle_and_house(build: int) -> None:
    digest = _digest(build)

    assert labels.label_in_snapshot(digest, "technology", "101") == "Feudal Age"
    assert labels.label_in_snapshot(digest, "technology", "102") == "Castle Age"
    assert labels.label_in_snapshot(digest, "building", "70") == "House"
    assert labels.label_in_snapshot(digest, "unit", "83") == "Villager"


def test_an_id_the_snapshot_does_not_name_is_none_not_the_id() -> None:
    digest = _digest(185872)

    for kind in ("technology", "unit", "building"):
        assert labels.label_in_snapshot(digest, kind, _UNNAMED_ID) is None


def test_a_digest_no_loaded_snapshot_has_names_nothing() -> None:
    """The contrast: build 185872 has a promoted snapshot, and this digest is not its."""
    assert labels.label_in_snapshot("sha256:" + "ab" * 32, "technology", "101") is None


def test_line_break_markup_in_a_vendored_name_is_collapsed() -> None:
    """The source writes "Town<br>\\nCenter"; the page must not show markup."""
    digest = _digest(185872)

    assert labels.label_in_snapshot(digest, "building", "109") == "Town Center"
    assert labels.label_in_snapshot(digest, "building", "562") == "Lumber Camp"


def test_the_unnamed_ids_are_outside_every_snapshot() -> None:
    for loaded in snapshot.load_all_snapshots():
        for kind in ("technology", "unit", "building"):
            assert labels.label_in_snapshot(loaded.identity.digest, kind, _UNNAMED_ID) is None
            assert labels.label_in_snapshot(loaded.identity.digest, kind, "987654322") is None
            assert labels.label_in_snapshot(loaded.identity.digest, kind, "987654323") is None
