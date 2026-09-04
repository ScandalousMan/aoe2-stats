"""The id-to-name mapping for Relic's `getRecentMatchHistory` `matchtype_id` (T410, defect fix).

**This is a different id space from `leaderboards.py`.** `GET /community/leaderboard/
getPersonalStat` (`packages/providers/.../relic/profile.py`) carries a bare `leaderboard_id`
integer, and `leaderboards.py` (T033a) is the one place that names it — `routers/profiles.py`
still reads that table, unchanged by this module, for `GET /api/profiles`. `GET /community/
leaderboard/getRecentMatchHistory` (`packages/providers/.../relic/matches.py`) carries a different
bare integer, `matchtype_id`, which `RelicMatchHistoryProvider` stores unchanged into `matches.
leaderboard_id` (`packages/storage/.../models.py`'s `Match.leaderboard_id` — the *column* name
predates this distinction and does not itself imply the two ids share a vocabulary). Before this
module existed, `routers/matches.py`'s two serialisers named that column through `leaderboards.
leaderboard_name` anyway — the `getPersonalStat` table — so a real match with `matchtype_id 6`
("1v1 Random Map" in *this* id space) rendered the "Leaderboard 6" fallback, `leaderboards.py`'s
table having nothing at id 6 worth calling that.

**How the pairs below were established.** `matchtype_id` carries no name of its own from Relic.
aoe2companion's enrichment endpoint (`packages/providers/.../companion/`) answers each match with
its own `internalLeaderboardId` and a human `leaderboardName` alongside it. A real match
(474746656) confirmed by hand that these are the same id Relic calls `matchtype_id`: Relic's own
`getRecentMatchHistory` names that match's `matchtype_id` as `6`, and companion's
`internalLeaderboardId` for the identical match is also `6`, carrying
`leaderboardName: "1v1 Random Map"` — the same
derivation discipline `civilizations.py` documents (join two independently captured sources on a
shared key, on the shared key alone, never inferred from a game rule). `apps/api/tests/
test_match_types.py` re-runs the equivalent join against this repository's own frozen fixtures
(`packages/providers/fixtures/relic/get_recent_match_history.json` and `packages/providers/
fixtures/companion/matches.json`) wherever they happen to overlap on a nameable id.

Only ids confidently derived this way are listed — 0 ("Unranked"), 6 ("1v1 Random Map"), 7 and 9
(both "Team Random Map": distinct team sizes share one name in this id space, unlike
`leaderboards.py`'s table, which keeps a single `4` for every "Team Random Map" size). An id this
module cannot name still gets a response rather than an error: it renders as "Leaderboard <id>",
the identical fallback wording `leaderboard_name` already used before this fix, so an unknown id
degrades exactly as it did before rather than showing a guessed name (FR-020). Extending this table
further is future work gated on evidence, matching `leaderboards.py`'s and `civilizations.py`'s own
"never a guess" discipline.
"""

from __future__ import annotations

KNOWN_MATCH_TYPE_NAMES: dict[int, str] = {
    0: "Unranked",
    6: "1v1 Random Map",
    7: "Team Random Map",
    9: "Team Random Map",
}


def match_type_name(matchtype_id: int) -> str:
    return KNOWN_MATCH_TYPE_NAMES.get(matchtype_id, f"Leaderboard {matchtype_id}")
