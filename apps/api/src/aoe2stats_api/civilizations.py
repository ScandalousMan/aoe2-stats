"""The civilisation id-to-name mapping for AoE2 DE (T070c, corrected T070g, extended T070i).

`getRecentMatchHistory`'s per-player rows (`matchhistorymember[].civilization_id`,
`docs/data-sources.md` §1) carry a bare integer, never a name — Relic does not return one from this
endpoint. `packages/storage/.../models.py`'s `MatchPlayer.civ_id` stores that integer unchanged,
and `routers/matches.py` (T070) reads it when it assembles both `GET /api/matches` and
`GET /api/matches/{game_id}`, so the front end is served a name and never hand-maintains its own
copy of this table in a component module — the same discipline `leaderboards.py` (T033a) already
established for leaderboard ids, and this module is deliberately shaped the same way rather than
inventing a second pattern: a `KNOWN_*` table plus a lookup function that falls back to
"Civilisation <id>" for anything it does not recognise.

**T070c's table was wrong, not incomplete.** It named ids 1-13 with the original thirteen-strong
roster taken in alphabetical order and called that its one confidently-known range. Every one of
those thirteen entries was wrong: id 1 is Aztecs, not Britons; id 9 is Byzantines, not Persians;
id 12 is Cumans, not Turks. A confident wrong name is worse than the "Civilisation <id>" fallback
it was meant to avoid, because nothing about it looks unverified.

**How ids 0-44 below were actually established.** `packages/providers/fixtures/relic/
get_recent_match_history.json` (`matchHistoryStats[].matchhistorymember[]`, keyed by
`(match id, profile_id)`, carrying the bare `civilization_id`) was joined against
`packages/providers/fixtures/companion/matches.json` (`matches[].teams[].players[]`, same key,
carrying the enrichment source's own `civName`) — two independently captured, frozen fixtures for
the same real matches, one naming what the other only numbers. The join recovers 21 distinct
`civilization_id -> civName` pairs with zero conflicts (three ids recur across two different
matches and agree both times). All 21 are reproduced exactly by one rule: the civilisation's
zero-based position in the 45-name roster that predates the Three Kingdoms and Dynasties of India
civilisations, sorted alphabetically, with `Indians` kept at its *original* spelling rather than
the later renamed `Hindustanis` — `Hindustanis` would re-sort under H and move six ids. That the
rule reproduces the hole at id 21 too, where `Indians` alphabetises between `Incas` and `Italians`,
is what makes it a reading of the id space rather than a coincidence fitted to it. Id 21 is
therefore the one entry in this table whose *position* comes from one name (`Indians`, for sort
order) and whose *label* comes from another (`Hindustanis`, the name the game uses today) — do not
"fix" that mismatch; it is the derivation working as intended, not a leftover typo.

**What is measured and what is derived.** `apps/api/tests/test_civilizations.py` guards this table
with two tests that check different things. `test_table_matches_the_fixture_derived_join` re-runs
the join above and checks it against the table — this is the measurement, and it only ever reaches
the 21 ids the two fixtures happen to overlap on.
`test_table_matches_the_alphabetical_ordering_rule` re-derives all 45 entries from the rule those
21 measured pairs establish (the roster, sorted, with `Indians` at its original spelling) and
checks the *whole* table against that derivation. The second test does not add measurement the
first one lacks — it cannot, there is no more captured evidence — it only checks that every entry,
reached by a fixture or not, is what the rule the 21 measured pairs support would produce. Before
that test existed, an id outside the measured 21 could be edited to a wrong name —
`KNOWN_CIVILISATION_NAMES[12]` from `"Cumans"` to `"Turks"`, for instance — and the suite stayed
green. See `docs/data-sources.md` §1 for where this derivation is recorded.

**Ids 0-44 stop being reachable by the fixture join at 21 pairs and by the ordering rule at 44** —
the eight civilisations added between the Three Kingdoms and Dynasties of India expansions
(Jurchens, Khitans, Mapuche, Muisca, Shu, Tupi, Wei, Wu) sit outside the 45-name roster that rule
sorts, and no captured match in this repository's evidence uses one either. Asserting a plausible
order for them was exactly T070c's original error, so this module still does not: it does not
extend the ordering rule past id 44.

**Ids 45-60 (T070i): transcribed, not derived.** These are not covered by any rule or by this
repository's own fixtures — the roster and the join above simply do not reach them. Instead they
were cross-checked against SiegeEngineers/aoc-reference-data's `data/datasets/100.json`, a
community-maintained reference that states civilisation ids explicitly. That check confirmed every
one of the 45 ids already in this table (0-44) and 44 of their 45 labels — the one disagreement is
id 30, where the reference writes "Maya" and this table keeps "Mayans"; see the comment on that
entry below for why. Having confirmed the source agrees with everything this table could already
check, the fourteen ids below it that this repository has no other evidence for were read from it
and are transcribed here as individually-verified facts, in release order, not derived from any
rule the way 0-44 are:

```
45 Achaemenids   48 Shu    51 Jurchens   54 Thracians   58 Muisca
46 Athenians     49 Wu     52 Khitans    55 Puru        59 Mapuche
47 Spartans      50 Wei    53 Macedonians               60 Tupi
```

**Ids 56 and 57 are deliberately absent**, not merely unassigned. They are absent from the reference
dataset too — nothing checkable reaches them — so this module leaves them on the fallback rather
than guessing what sits between Puru (55) and Muisca (58). Inventing that gap is precisely the kind
of plausible-but-unchecked entry T070c already got wrong once; do not "complete" it later without
new evidence.

**The reference dataset is read, never vendored.** Unlike the MIT-licensed tech-tree data cited for
id 30 below, `aoc-reference-data` carries no licence at all (no `LICENSE` file, GitHub reports
`license: None`) — the same defect `docs/data-sources.md` already records against the aoe2companion
enrichment source. Its JSON is not copied into this repository in any form, and nothing in this
codebase fetches it at build or test time (constitution III forbids a network call outside
`packages/providers` regardless of licence). Only the fourteen id-name pairs above, read by hand and
transcribed as facts, live here. See `docs/data-sources.md` §1 for the same note in context.

An id of 61 or higher, and ids 56/57, still get a response, never a guess, rendered as
"Civilisation <id>", identical in shape to `leaderboard_name`'s own fallback. Extending this table
further is future work gated on evidence, not on guesswork.
"""

from __future__ import annotations

KNOWN_CIVILISATION_NAMES: dict[int, str] = {
    0: "Armenians",
    1: "Aztecs",
    2: "Bengalis",
    3: "Berbers",
    4: "Bohemians",
    5: "Britons",
    6: "Bulgarians",
    7: "Burgundians",
    8: "Burmese",
    9: "Byzantines",
    10: "Celts",
    11: "Chinese",
    12: "Cumans",
    13: "Dravidians",
    14: "Ethiopians",
    15: "Franks",
    16: "Georgians",
    17: "Goths",
    18: "Gurjaras",
    19: "Huns",
    20: "Incas",
    # id 21 was assigned when this civilisation was still called "Indians" — that original
    # spelling is what places it here, between Incas and Italians, rather than under H. The game
    # renamed it "Hindustanis"; this table follows the id's *sort position* from the old name but
    # its *display label* from the current one. See the module docstring before "fixing" this.
    21: "Hindustanis",
    22: "Italians",
    23: "Japanese",
    24: "Khmer",
    25: "Koreans",
    26: "Lithuanians",
    27: "Magyars",
    28: "Malay",
    29: "Malians",
    # T070i cross-checked this table against SiegeEngineers/aoc-reference-data, which spells this
    # civilisation "Maya". "Mayans" stays: it is the name the game itself displays, and the
    # MIT-licensed aoe2techtree data — generated from the game's own strings — spells it "Mayans"
    # too. This is a deliberate, checked divergence from that reference, not a stale name; do not
    # "fix" it toward "Maya".
    30: "Mayans",
    31: "Mongols",
    32: "Persians",
    33: "Poles",
    34: "Portuguese",
    35: "Romans",
    36: "Saracens",
    37: "Sicilians",
    38: "Slavs",
    39: "Spanish",
    40: "Tatars",
    41: "Teutons",
    42: "Turks",
    43: "Vietnamese",
    44: "Vikings",
    # Ids 45-60 below (T070i) are individually transcribed, in release order — not derived from
    # the alphabetical rule above, which stops at 44. See the module docstring's "Ids 45-60"
    # section for the cross-check that established them.
    45: "Achaemenids",
    46: "Athenians",
    47: "Spartans",
    48: "Shu",
    49: "Wu",
    50: "Wei",
    51: "Jurchens",
    52: "Khitans",
    53: "Macedonians",
    54: "Thracians",
    55: "Puru",
    # 56 and 57 are deliberately absent — they are missing from the cross-check source too. Do not
    # fill this gap by guessing what sits between Puru (55) and Muisca (58); see the module
    # docstring's "Ids 56 and 57" paragraph.
    58: "Muisca",
    59: "Mapuche",
    60: "Tupi",
}


def civilisation_name(civ_id: int | None) -> str | None:
    """`None` only when `civ_id` itself is `None` (no civilisation recorded for that participant)
    — never a guess otherwise, per the module docstring."""
    if civ_id is None:
        return None
    return KNOWN_CIVILISATION_NAMES.get(civ_id, f"Civilisation {civ_id}")
