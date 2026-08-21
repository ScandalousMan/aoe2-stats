"""The id-to-name mapping for AoE2 DE's standard ladders (T033a).

`GET /community/leaderboard/getPersonalStat` (`packages/providers/.../relic/profile.py`) carries a
bare `leaderboard_id` integer, never a name — Relic does not return one from this endpoint, and
`docs/data-sources.md` §1 does not record one either. `profile-summary.md`'s anatomy still requires
a `LeaderboardName` per entry (FR-008), so something has to name these ids, and this module is the
one place that does: `routers/profiles.py` reads it when it assembles `GET /api/profiles`, so the
front end (`apps/web/src/features/profile`) is served a name and never hand-maintains its own copy
of this table (see T033a's remediation note — a duplicate copy in a component module is exactly
what the three-homes rule in `CLAUDE.md` exists to prevent).

Only the ladders this module can name with confidence are listed. This is static game reference
data — AoE2 DE's ladder ids are stable across patches — not a value that changes call to call, so
a hand-maintained table here carries none of the staleness risk `docs/data-sources.md` exists to
track; there is nothing to re-measure. An id this map does not recognise still gets a response
rather than an error: it renders as "Leaderboard <id>" rather than a guessed name that might be
wrong.
"""

from __future__ import annotations

KNOWN_LEADERBOARD_NAMES: dict[int, str] = {
    1: "1v1 Death Match",
    2: "Team Death Match",
    3: "1v1 Random Map",
    4: "Team Random Map",
    13: "1v1 Empire Wars",
    14: "Team Empire Wars",
}


def leaderboard_name(leaderboard_id: int) -> str:
    return KNOWN_LEADERBOARD_NAMES.get(leaderboard_id, f"Leaderboard {leaderboard_id}")
