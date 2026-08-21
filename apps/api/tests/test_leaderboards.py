"""Unit tests for `aoe2stats_api.leaderboards` (T033a).

This is the one place `leaderboard_id -> name` is hand-maintained (see the module docstring): a
self-contained unit test, no database and no network, mirroring the front end's own former test
of the same table (`apps/web/src/features/profile/leaderboards.test.ts`).
"""

from aoe2stats_api.leaderboards import leaderboard_name


def test_names_a_known_leaderboard_id() -> None:
    assert leaderboard_name(3) == "1v1 Random Map"


def test_falls_back_to_leaderboard_id_for_an_unrecognised_id() -> None:
    """An id this table does not carry renders as "Leaderboard <id>", never a guessed name that
    might be wrong (module docstring)."""
    assert leaderboard_name(999) == "Leaderboard 999"
