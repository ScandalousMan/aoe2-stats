# Owner readings — Phase 8

The values that no source an agent may read states, for the owner to read from the running game
(or, where the game does not display it, the Fandom wiki), per FR-022c and FR-030's strong form.
Phase 8's batches add rows; T772 and T774 turn each answered row into a modelled effect. A row is
**open** until its four answer columns are filled. Do not guess a value to close a row.

How to read a value: start a solo game or open the scenario editor with the civilisation named,
reach the age named, research the technologies named, and read the tooltip of the entity named.
If neither the game nor the Fandom wiki shows the value, write `unreadable` and where you looked:
the row then becomes an enumerated limit (FR-022b) instead of blocking promotion.

## Open values

| Build  | Civilisation | Entity | Field | Conditions | Why no source settles it | Sources searched | Value read | Where read | Build shown | Date |
| ------ | ------------ | ------ | ----- | ---------- | ------------------------ | ---------------- | ---------- | ---------- | ----------- | ---- |
| 185872 | Slavs | Castle and Watch Tower line (buildings 82, 79, 234, 235) | cost | Detinets researched | Detinets replaces 40% of the stone with wood; the wood is never stated | pack (T746); publisher's notes (T767): update 61321 introduces Detinets with the pack's own sentence, "Replaces 40% of Castles' and Towers' stone cost with wood, costs 400w 200g", and no later page changes or sizes it |  |  |  |  |
| 185872 | Persians | Archer line | cost | Kamandaran researched | the replacement amount is never stated | pack (T746); publisher's notes (T767): update 162286 states "Archer-line costs 60 wood -> 50 wood", update 34699 the earlier 50 -> 60. **Settled for build 185872 and transcribed by T767 as 50 wood, no gold**; the reading as a total is flagged in the row and is for the owner's validation sample (T770). Kept here only until build 180059's and 177723's rows below are closed by T773 | 50 wood, no gold (total) | publisher's notes, update 162286 | not a game reading | 2026-10-22 |
| 180059 | Persians | Archer line | cost | Kamandaran researched | the replacement amount is never stated | pack (T645); publisher's notes (T767): update 162286 (earlier than build 180059) states the same 50 wood, no later page changes it. Not transcribed: T773 does it for this build's snapshot |  |  |  |  |
| 177723 | Persians | Archer line | cost | Kamandaran researched | the replacement amount is never stated | pack (T645; this snapshot's effects.toml repeats build 180059's content byte for byte); publisher's notes (T767), as for build 180059; no Phase 8 task models this snapshot |  |  |  |  |
| 185872 | Sicilians | the Watch Tower line (79, 234, 235), the Bombard Tower (236) and the Krepost (1251) | production_time | none | the bullet never lists which buildings "Fortifications" names; the notes state the Castle and the Donjon only | pack (T746); publisher's notes (T767): update 81058 and update 111772 (Castle; Donjon "83 seconds after civilization bonus"), no other page lists a fortification for this bonus. The Castle (82) and the Donjon (1665) are transcribed by T767 |  |  |  |  |
| 185872 | Chinese | Castle Age and Imperial Age advances (technologies 102, 103) | cost | none | "Technologies cost -5/10/15%" never says whether an Age advance is a technology it discounts; the Feudal Age advance is researched in the Dark Age, which the bonus does not cover, so it needs no answer | pack (T767); publisher's notes (T767): update 87863 changes the percentages only |  |  |  |  |
| 185872 | Turks | Artillery (10), Bombard Tower (64), Elite Janissary (369), Elite Cannon Galleon (376) | cost | none | "Gunpowder technologies costs -50%" never says which technologies it names. The four are the Turks' technologies that concern a unit or building the pack's Chemistry string lists as a Gunpowder Unit, or an upgrade of one; a technology outside them would be answered at the baseline, so the owner is asked which of the Turks' technologies the game discounts, not only these four | pack (T767); publisher's notes (T767): no page defines the phrase |  |  |  |  |
| 185872 | Turks | Janissary (46), Elite Janissary (557), Conquistador (771), Elite Conquistador (773) | production_time | none | the team bonus "Gunpowder Units train +25% faster" speeds Gunpowder Units; the pack calls these Foot Gunners and Mounted Gunners and never calls them Gunpowder Units (it names the Hand Cannoneer, Cannon Galleon, Bombard Cannon and Bombard Tower). The effect model scopes a refusal to the Turks, so an ally's Conquistador is not refused | pack (T767); publisher's notes (T767): no page lists the class |  |  |  |  |
| 185872 | Aztecs | War Galley (21), Demolition Ship (527), Fire Ship (529), Fast Fire Ship (532), Galley (539), Fire Galley (1103), Demolition Raft (1104), Hulk (2626), War Hulk (2627), Carrack (2628), Catapult Galleon (2633) and the Monk (125) | production_time | none | "Military Units train +15% faster" never defines the class; the pack's building strings put Infantry, Ranged Soldiers, Cavalry, Siege Weapons and unique units at the Barracks, Archery Range, Stable, Siege Workshop, Castle, Donjon and Krepost, which T767 models, and say nothing of the Dock's warships or the Monastery's Monk | pack (T767); publisher's notes (T767): update 125283 raised the percentage from 11 to 15 and defines no class |  |  |  |  |
| 185872 | Magyars | Magyar Huszar (869) and Elite Magyar Huszar (871) | cost | Corvinian Army researched | "Magyar Huszar gold cost is replaced by additional food cost" never says how much food; the unit's base cost is 35 food 45 gold | pack (T768); publisher's notes (T768): update 95810 is the one page that names the effect (it changed "Magyar Huszar cost no gold" to the replacement, and the base cost from 80 food 10 gold to 35 food 45 gold) and states no figure; no later page changes it. A total of 80 food would be an inference no source states and is not transcribed |  |  |  |  |
| 185872 | Malay | Militia-line (74, 75, 77, 473, 567) | cost | Forced Levy researched | "Militia-line gold cost is replaced by additional food cost" never says how much food; the line's base cost is 50 food 20 gold | pack (T768); publisher's notes (T768): no page of the 77 fetched names Forced Levy |  |  |  |  |
| 185872 | Berbers | the Castle's units and technologies in the Berbers' tree: Trebuchet (331, and the identifier 1690 the snapshot aliases to it), Petard (440), Camel Archer (1007), Elite Camel Archer (1009), Conscription (315), Hoardings (379), Spies/Treason (408), Elite Camel Archer (565), Kasbah (578), Maghrebi Camels (579) | production_time | Kasbah researched, and the owner's team | "Kasbah (Team Castles work +25% faster)" needs the technology researched by the owner and the owner's team together, and the effect model carries one condition per effect, so it cannot be written as a rule. Writing it as `researched` alone would leave an ally's Castle unaccelerated; as `team` alone it would accelerate it whether or not Kasbah was researched. The value (+25% faster) is stated; what is missing is a way to say it. A modelled=no row is scoped to its owner, so an ally's Castle production time is answered at the baseline whether or not Kasbah was researched | pack (T768); publisher's notes (T768): only the 185872 page names the technology, in a note on notifications ("technologies that affect other players ... Kasbah"), and no page changes the bonus. **This is not a value the owner can read in the game: it is closed by an amendment of the effect model (a combined condition) or by the owner's ruling on an approximation** |  |  |  |  |

"Sources searched" names what was read before the row was opened. T767 searched the publisher's
notes (the Definitive Edition update pages `ageofempires.com` lists, fetched 2026-10-22) for the
four rows T746 left, and closed the part of each they settle: Kamandaran for build 185872, the
Donjon and the Castle of the Sicilians' Fortifications. T768 searched the same 77 pages for every
value the pack does not size in its twelve civilisations and closed the part of each they settle
(the Portuguese team bonus excludes Age Up; the Ethiopians' Outposts lose their stone cost; the
Koreans' discount reaches the War Wagon; the Incas' food discount lists its units); the three rows
above are what they do not settle. The Fandom wiki was not read; it is the owner's. The Persians row of build 185872 is a closed row: its value came from the publisher's
notes and not from the game, and it is listed so the owner can compare it with the game.

## Validation sample

Written by T770: one value per civilisation, for the owner to compare with the game. A difference is
recorded as a disagreement and the game's value is stored (FR-022c).

| Civilisation | Entity | Age | Technologies researched | Value the snapshot answers | Value read | Date |
| ------------ | ------ | --- | ----------------------- | -------------------------- | ---------- | ---- |

## Production

Written by T775 after each deployed promotion.

| Date | Build | Snapshot label | Blocking gaps in the window |
| ---- | ----- | -------------- | --------------------------- |
