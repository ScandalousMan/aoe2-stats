"""The civilisation id-to-name mapping for AoE2 DE (T070c).

`getRecentMatchHistory`'s per-player rows (`matchhistorymember[].civilization_id`,
`docs/data-sources.md` §1) carry a bare integer, never a name — Relic does not return one from this
endpoint. `packages/storage/.../models.py`'s `MatchPlayer.civ_id` stores that integer unchanged,
and `routers/matches.py` (T070) reads it when it assembles both `GET /api/matches` and
`GET /api/matches/{game_id}`, so the front end is served a name and never hand-maintains its own
copy of this table in a component module — the same discipline `leaderboards.py` (T033a) already
established for leaderboard ids, and this module is deliberately shaped the same way rather than
inventing a second pattern: a `KNOWN_*` table plus a lookup function that falls back to
"Civilisation <id>" for anything it does not recognise.

**Why only thirteen entries.** Unlike `leaderboards.py`'s ladders, AoE2 DE's civilisation roster has
grown across many expansions since this feature's own `docs/data-sources.md` was last measured, and
this module has no verified source to check a later id against — asserting one anyway is exactly
the failure `docs/data-sources.md`'s own opening rule exists to prevent ("a number that exists in
two files will be wrong in one of them" applies just as much to a number this repository has never
actually measured). The thirteen listed below are the game's original roster, present since its
first release and unchanged by every expansion since (the standard ids repeated identically across
essentially every AoE2 tool and documented civilisation list) — the one range this module can name
with genuine confidence. An id outside it still gets a response, never a guess: it renders as
"Civilisation <id>", identical in shape to `leaderboard_name`'s own fallback. Extending this table
is future work, not a gap this module hides.
"""

from __future__ import annotations

KNOWN_CIVILISATION_NAMES: dict[int, str] = {
    1: "Britons",
    2: "Byzantines",
    3: "Celts",
    4: "Chinese",
    5: "Franks",
    6: "Goths",
    7: "Japanese",
    8: "Mongols",
    9: "Persians",
    10: "Saracens",
    11: "Teutons",
    12: "Turks",
    13: "Vikings",
}


def civilisation_name(civ_id: int | None) -> str | None:
    """`None` only when `civ_id` itself is `None` (no civilisation recorded for that participant)
    — never a guess otherwise, per the module docstring."""
    if civ_id is None:
        return None
    return KNOWN_CIVILISATION_NAMES.get(civ_id, f"Civilisation {civ_id}")
