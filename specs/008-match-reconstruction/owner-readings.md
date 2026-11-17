# Owner readings — match reconstruction

What this feature needs read in the game, by playing a committed recording back (FR-019, FR-026,
contracts/playback-readings.md). This file asks; it holds no answer. Each answer is transcribed into
`tests/fixtures/replays/<recording>.playback.toml` with who read it, when, and the build the game
showed, and that file is the only place the value is written.

Players are named by their slot in the recording and their civilisation, as the game's lobby list
and score panel show them. Times are match time as the replay's clock shows it. Where a value cannot
be read in the game, answer `unreadable` and say where you looked: the rule it checks then stays a
candidate.

**The order matters.** O1 and O2 close gate G1 (plan.md), which every published spending and arrival
waits on. The rest can follow.

| Recording | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
| --------- | ------ | ------ | ------ | ------ |
| 500546441 | Saracens | Malians | | |
| 504695319 | Franks | Persians | Teutons | Tatars |
| 511523321 | Slavs | Sicilians | | |

## O1 — Each age-up: the queue ahead of it, and when it arrived

For each row: pause the replay at the click time, select that player's Town Center, and read **how
many items are in its queue ahead of the age-up**, and what they are (Villagers, a technology). Then
read **the time the age was reached**, from the post-game timeline when the replay ends, or from the
age notification during playback.

Checks D-AGE-1 and D-HOUSE-0, and is G1's main evidence (research R2: ten of these arrivals are
contradicted by the recording's own proofs under the current model).

| Request | Recording | Slot | Age-up | Click at | Town Center object (for the record) |
| ------- | --------- | ---- | ------ | -------- | ----------------------------------- |
| O1.1 | 500546441 | 1 | Feudal Age | 6:41 | 4191 |
| O1.2 | 500546441 | 2 | Feudal Age | 6:43 | 4198 |
| O1.3 | 500546441 | 1 | Castle Age | 15:15 | 4191 |
| O1.4 | 500546441 | 2 | Castle Age | 19:28 | 4198 |
| O1.5 | 500546441 | 2 | Imperial Age | 34:02 | 7281 |
| O1.6 | 500546441 | 1 | Imperial Age | 34:30 | 4191 |
| O1.7 | 504695319 | 2 | Feudal Age | 7:57 | 6072 |
| O1.8 | 504695319 | 1 | Feudal Age | 8:16 | 6066 |
| O1.9 | 504695319 | 3 | Feudal Age | 8:29 | 6078 |
| O1.10 | 504695319 | 4 | Feudal Age | 9:20 | 6084 |
| O1.11 | 504695319 | 2 | Castle Age | 12:40 | 6072 |
| O1.12 | 504695319 | 4 | Castle Age | 14:07 | 6084 |
| O1.13 | 504695319 | 3 | Castle Age | 15:41 | 6078 |
| O1.14 | 504695319 | 1 | Castle Age | 16:19 | 6066 |
| O1.15 | 504695319 | 2 | Imperial Age | 31:41 | 20607 |
| O1.16 | 504695319 | 4 | Imperial Age | 34:00 | 20137 |
| O1.17 | 504695319 | 3 | Imperial Age | 38:09 | 20479 |
| O1.18 | 504695319 | 1 | Imperial Age | 40:50 | 6066 |
| O1.19 | 511523321 | 2 | Feudal Age | 6:28 | 3757 |
| O1.20 | 511523321 | 1 | Feudal Age | 6:44 | 3750 |
| O1.21 | 511523321 | 1 | Castle Age | 17:37 | 3750 |
| O1.22 | 511523321 | 2 | Castle Age | 18:50 | 3757 |

## O2 — A command naming several buildings

500546441, slot 2 (Malians), at **15:37**: one command queues one unit 4 (Archer) with two Archery
Ranges selected. Select each of slot 2's Archery Ranges just before and just after 15:37, and read
**how many Archers each one gained**. Repeat at 15:41 and 15:43, the next two such commands.

Checks D-DIST-1 and decides whether a command's amount is spent once or once per building (research
R1).

## O3 — A Sicilian unit before its age

511523321, slot 2 (Sicilians), at **10:25**: the recording orders unit 1658 (Serjeant) before slot
2 clicks Castle Age at 18:50. Pause at 10:30, select the building training it, and read **whether a
Serjeant is in training, and the player's age** shown at the top of the screen.

Checks P1 and the knowledge base's age requirement for that unit (research R3).

## O4 — The starting state

In each recording, at **0:00** (or the first frame the replay shows), for each slot read: **food,
wood, stone, gold**, **population and population cap** (the "current / cap" figure), **the units
standing** (how many Villagers, which scout), and **the age**. Then read the lobby's starting age and
starting resources settings, from the game's match information screen if it shows them.

Checks the starting-state decoder and the starting-objects table (research R4, FR-026).

## O8 — The starting objects table's open values

Requested 2026-11-17 for the starting-objects table of the snapshot `aoe2techtree-188329-starting-objects`
(research R4, FR-026, T925). The vendored pack states the objects a civilisation's bonus adds and
states no baseline; the table therefore carries one `[[open]]` row per value below and guesses none
(docs/data-sources.md section 6, "Starting objects"). Each answer is transcribed into
`tests/fixtures/replays/<recording>.playback.toml` as O4's are, and then into a superseding snapshot.

**O8.1 — The baseline.** For each recording's lobby preset (the same one for all three, research R4),
O4's 0:00 reading of the units and buildings standing, with **how many Villagers, which scout, and
which buildings (the Town Center and any other)**, for a slot whose civilisation adds no starting
object. The table's baseline row for that preset is transcribed from it. No new reading is needed
if O4 already carries the counts.

**O8.2 — The other presets.** In the game's lobby, list **every value the starting-resources
setting and the starting-age setting offer**, and, for each value that changes what a participant
starts with in units or buildings (not in stockpiles), start a match and read the units and
buildings standing at 0:00. A value not read stays an open row; a recording carrying it gaps its
starting objects.

**O8.3 — The six civilisation bonuses.** The pack says the Chinese start with +3 Villagers, the
Mayans with +1 Villager, the Georgians with a Mule Cart, the Gurjaras with 2 Forage Bushes, the
Incas' team with a free Llama and the Huns' first Town Center on a Nomadic map spawns a scouting
Horse. None of the committed recordings has one of these civilisations (see the table at the top).
In a custom game with each civilisation, read at 0:00 **the Villagers, the other units and the
objects standing**, and say whether the bonus differs under a preset other than the one read in
O8.1. If a civilisation cannot be started, answer `unreadable`; its row stays as the pack states it,
unverified.

**O8.4 — The stockpile each starting-resources value grants.** For each value the lobby's
starting-resources setting offers (the list O8.2 asks for), read at 0:00 **the food, wood, stone and
gold** of a slot whose civilisation has no stockpile bonus. The knowledge base states none of these,
so the starting state's derived stockpile is a gap and the `starting-resources-agree` invariant
compares nothing until this is answered (T927). The decoded stockpile of the committed recordings is
not an answer: the invariant exists to check it against an independent source.

## O5 — Three deletions

For each, pause just before the time given, find the object the player deletes, and read **what it
is** (unit or building, and which), **whether it is a foundation with no construction progress**,
and **which placement it came from** (when it was placed).

| Request | Recording | Slot | Deletion at | Why this one |
| ------- | --------- | ---- | ----------- | ------------ |
| O5.1 | 500546441 | 2 | 0:04 | an object no earlier command names |
| O5.2 | 504695319 | 1 | 31:35 | an object the player targeted about six seconds after placing a building |
| O5.3 | 511523321 | 2 | 7:53 | an object no earlier command names |

Checks D-TIE-1 and D-REFUND-1 (research R6).

## O6 — Population, losses and idle time

Requested 2026-11-15 for the estimates of US6 (research R16): these readings measure how far each
estimate is from the game. They close no gate, and an estimate that differs from a reading is
recorded with the difference, not failed. The population phase (plan.md, phase 8) reuses the same
readings to check its candidate rules, and adds its own here once they are written (research R5).

**O6.1 — The end-of-match statistics.** In each recording, let the replay run to its end and open
the statistics screen. For each slot, from the military statistics, read **units lost** and
**buildings lost**, and also **units killed**, **buildings razed** and **units converted** if the
screen shows them. If the replay shows no statistics screen at its end, answer `unreadable` and say
what it shows instead. Whether the playback shows this screen is not established; that is part of
what is asked.

| Request | Recording | Slots |
| ------- | --------- | ----- |
| O6.1.1 | 500546441 | 1, 2 |
| O6.1.2 | 504695319 | 1, 2, 3, 4 |
| O6.1.3 | 511523321 | 1, 2 |

Measures the estimated unit losses and the estimated buildings destroyed. The game's figures are
wider than the estimates (every building, not only producing ones), and each recorded error says
so.

**O6.2 — Population at stated times.** In each recording, pause at each time below and, for each
slot, read the **population figure as "current / cap"** shown at the top of the screen when that
player is selected.

| Request | Recording | Pause at |
| ------- | --------- | -------- |
| O6.2.1 | 500546441 | 10:00, 20:00, 30:00, 40:00, 50:00 |
| O6.2.2 | 504695319 | 10:00, 20:00, 30:00, 40:00, 50:00 |
| O6.2.3 | 511523321 | 10:00, 20:00, 30:00 |

Measures the estimated living population, and tells whether the lobby's population limit or the houses
bound the player at that moment.

**O6.3 — Idle Town Centers.** Not requested yet. Once the estimates' goldens exist, the estimates
phase adds here a few stretches the estimate calls idle and a few it calls busy, each a Town Center
to select at a stated time and its queue to read.

## O7 — A recording that carries a cancellation (optional, no fixture has one)

No committed recording contains a unit cancellation, so the adapter cannot prove the payload's
layout and D-CANCEL-1 cannot be checked. If one of your own recorded games has you cancel a queued
Villager or soldier, say which match; it can be committed under 006's basis for committed reference
recordings. If none does, play one game in which you queue three Villagers and cancel the last two
from the Town Center's queue panel, and note the match time. Nothing else in this feature waits on
it.
