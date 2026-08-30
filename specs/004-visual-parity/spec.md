# Feature Specification: Visual Parity — Game Assets and Rich Profile/Match Presentation

**Feature Branch**: `004-visual-parity`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "Now that constitution 5.0.0 permits game asset packs in the repository, bring the profile page and match history up to visual parity with third-party AoE2 sites (e.g. aoe2insights). Today the app renders a bare numeric profile id with no game imagery; peers show persona name, country flag, avatar, civilisation icons, map icons, player colours, rating and rating change, and which team won."

## Context

For the same profile (`1807091`) and the same matches, a comparable third-party site shows the
player's name, their country, their civilisation for each game, the map, each player's colour, the
rating and how it moved, and which side won — while this application shows the raw number `1807091`
as both name and subtitle, "No ratings yet", no site navigation, and no game imagery at all. The
product looks materially poorer than every peer despite holding the same data.

The data is already there. Feature 001 ingests and stores, per its data model: `players.alias`
(persona name), `players.country`, and per match `match_players.civ_id`, `color_id`, `result`,
`rating`, `rating_diff`, `team_id`, and `matches.map_name`, `leaderboard_id`, `started_at`,
`completed_at`. What was missing until now was (a) the presentation of that data and (b) the game
imagery to make it legible — the latter blocked by the pre-5.0.0 constitution, which forbade copying
any game asset into the repository. Constitution 5.0.0 (principle X) lifts that block under a
non-commercial + disclaimer + per-pack-licence gate. This feature is the presentation and the
assets; it changes nothing about what is ingested.

## Clarifications

### Session 2026-08-30

- Q: How should the player avatar be handled, given it is available from the companion provider
  (`avatarhash`) but is not stored in the data model? → A: Display it as peers do, by referencing the
  Steam avatars CDN at render time — the URL is `https://avatars.steamstatic.com/<avatarhash>_full.jpg`,
  built from the hash. The hash is not a game asset and is not copied into the repository; it must be
  surfaced to the client (it originates from the companion provider, enrichment-only and degradable).
- Q: How deep should the map representation go — a compact icon per map, or a rendered minimap
  thumbnail per map as peers show? → A: A minimap thumbnail per map. This is the larger asset set and
  licence surface, and it is in scope; the packs are chosen and licence-recorded at planning under the
  FR-011 gate.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - A match is legible at a glance (Priority: P1)

A user opens a player's match history. Instead of rows of numbers, each match shows the
civilisation each side played (as an icon and name), the map, each player's in-game colour, who won
and who lost, and how the rating moved (+/−). The user understands the match without decoding any
identifier.

**Why this priority**: this is the flagship parity gap and the reason the constitution was amended —
civilisation and map imagery are exactly what principle X used to forbid. It turns data the product
already holds into the thing users actually come for. It is the MVP: shipping only this already
closes most of the visible gap with peers.

**Independent Test**: load a profile with known matches; confirm each row presents civilisation
(icon + name), map, player colours, outcome (winner distinguished from loser), and rating change,
all derived from data already stored, with no numeric `civ_id`/`color_id`/`map` id shown to the user.

**Acceptance Scenarios**:

1. **Given** a match whose `civ_id` values are covered by the civilisation mapping, **When** the user
   views the match, **Then** each participant shows their civilisation icon and name, not a number.
2. **Given** a match with a recorded `result` per participant, **When** the user views it, **Then**
   the winning side is visually distinguished from the losing side.
3. **Given** a match with `rating` and `rating_diff` for the viewed player, **When** the user views
   it, **Then** the rating and its signed change (e.g. `922 (+16)`, `921 (−15)`) are shown, with the
   direction distinguishable without relying on colour alone.
4. **Given** a `map_name` present on the match, **When** the user views it, **Then** the map is shown
   with its name and its map imagery.
5. **Given** each participant's `color_id`, **When** the user views the match, **Then** each player
   is shown in the canonical in-game player colour for that id.

---

### User Story 2 - A profile says who the player is (Priority: P2)

A user opens a profile. It shows the player's name and country rather than a bare numeric id, with
ratings presented clearly (and a clear, non-alarming empty state when a profile genuinely has no
ranked rating yet).

**Why this priority**: the most embarrassing single element in the current product is the number
`1807091` standing in for a person. It depends on almost no new imagery (a country flag is not a
game asset) and is a small, high-visibility win — but it sits behind US1 because match legibility is
the larger draw.

**Independent Test**: load a profile whose `alias` and `country` are stored; confirm the name and a
country flag are shown, the numeric id is demoted to a secondary reference, and a profile with no
ranked rating shows the existing "No ratings yet" explanation unchanged.

**Acceptance Scenarios**:

1. **Given** a profile with a stored `alias`, **When** the user views it, **Then** the alias is the
   heading and the numeric id is secondary, not the heading.
2. **Given** a profile with a stored `country`, **When** the user views it, **Then** the country flag
   is shown beside the name.
3. **Given** a profile with no stored `alias`, **When** the user views it, **Then** the numeric id is
   shown as the name (graceful fallback), never a blank heading.

---

### User Story 3 - The site has a way around it (Priority: P3)

A user lands on any page and has a header with primary navigation, so the app reads as a site rather
than a single stranded view. The existing footer (which carries the Microsoft "Game Content Usage
Rules" disclaimer) remains.

**Why this priority**: chrome improves coherence but blocks no data comprehension, so it ranks below
the two content stories. It has no data or asset dependency.

**Independent Test**: from any route, confirm a header with working primary navigation is present and
the footer disclaimer is still rendered.

**Acceptance Scenarios**:

1. **Given** any page, **When** it renders, **Then** a header with primary navigation is present.
2. **Given** any page, **When** it renders, **Then** the footer with the Game Content Usage Rules
   disclaimer is still present.

---

### Edge Cases

- **An identifier the asset pack does not cover.** A new expansion adds a civilisation whose `civ_id`
  is outside the shipped pack (the exact case feature 002 exists for). The view MUST degrade to the
  readable label for that id (name if the mapping has it, else the bare id) and MUST NOT show a broken
  image. The same rule applies to an unknown `map_name` or an out-of-range `color_id`.
- **Missing enrichment.** `alias` or `country` absent → fall back to the numeric id / omit the flag;
  never render a blank or a placeholder that looks like an error.
- **Genuinely no rating.** The "No ratings yet" state is a real, correct outcome (profile `1807091`
  has it) and MUST remain a calm explanation, not an error.
- **Draw / unfinished result.** A `result` that is neither win nor loss MUST render as its own
  neutral state, not silently as a loss.
- **Theme.** All new imagery and colour treatments MUST remain legible in both light and dark theme.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The match view MUST present each participant's civilisation as an icon and name derived
  from `civ_id`, using the civilisation mapping owned by feature 002; no raw `civ_id` is shown.
- **FR-002**: The match view MUST present the map as a minimap thumbnail and name derived from
  `map_name`.
- **FR-003**: The match view MUST present each participant in the canonical in-game player colour for
  their `color_id`.
- **FR-004**: The match view MUST distinguish the winning side from the losing side, derived from
  `result`, and MUST render a neutral state for a non-win/non-loss result.
- **FR-005**: The match view MUST show the viewed player's `rating` and signed `rating_diff`, with
  direction conveyed by more than colour alone.
- **FR-006**: The match view SHOULD show match metadata already stored — ladder (`leaderboard_id`),
  duration (`started_at`→`completed_at`), and date — where it aids legibility.
- **FR-007**: The profile view MUST show `alias` as the primary name and demote the numeric id to a
  secondary reference; when `alias` is absent it MUST fall back to the numeric id.
- **FR-008**: The profile view MUST show a country flag derived from `country` when present, and omit
  it cleanly when absent.
- **FR-008a**: The profile view MUST show the player's avatar, referenced from the Steam avatars CDN
  at `https://avatars.steamstatic.com/<avatarhash>_full.jpg` built from the avatar hash supplied by
  the companion provider; when the hash is unavailable it MUST show a neutral placeholder, never a
  broken image. The avatar hash is not a game asset and is not copied into the repository.
- **FR-009**: The application MUST present a header with primary navigation on every page, and MUST
  keep the existing footer and its Game Content Usage Rules disclaimer.
- **FR-010**: Any identifier not covered by an asset pack or mapping (`civ_id`, `map_name`,
  `color_id`) MUST degrade to a readable label and MUST NOT produce a broken or missing image.
- **FR-011**: Every game-asset pack copied into the repository MUST record its source and its
  permitted usage (per constitution X and feature 002's discipline). A pack whose licence is not
  recorded MUST NOT be added.
- **FR-012**: The application MUST remain strictly non-commercial and MUST keep the Microsoft "Game
  Content Usage Rules" disclaimer in both the README and the site footer.
- **FR-013**: All new or changed presentation MUST use design-system tokens only (no hard-coded
  style values) and every new or changed component MUST have a Storybook story and pass visual
  regression.
- **FR-014**: The front end MUST obtain all data it presents from the existing API and MUST NOT
  introduce any outbound network call outside `packages/providers`; this feature MUST NOT change what
  data is ingested nor degrade the capture pipeline.
- **FR-015**: The avatar hash originates from the companion provider (a `packages/providers` source,
  enrichment-only and degradable) and MUST be surfaced through the API to the client. The image itself
  is loaded by the browser from the Steam avatars CDN (a client-side image reference, not a backend
  provider call), so it does not constitute an outbound connection from `apps/*` or `packages/core`
  under FR-014. When the hash is absent, the feature MUST degrade gracefully (FR-008a) rather than
  block the profile view.
- **FR-016**: The map is represented as a minimap thumbnail per map (not a compact glyph). The
  thumbnails are a game-asset pack subject to the FR-011 licence gate; an unknown `map_name` degrades
  per FR-010.

### Key Entities _(include if feature involves data)_

- **Asset pack**: a set of game images copied into the repository (e.g. civilisation icons, map
  imagery, or a colour definition), with a recorded source, licence, permitted-usage note, and the
  identifier space it is keyed by (`civ_id`, `map_name`, `color_id`). The unit the constitution X
  licence gate applies to.
- **Civilisation presentation**: the icon and display name for a `civ_id`, keyed by the same ids as
  feature 002's mapping.
- **Map presentation**: the minimap thumbnail and display name for a `map_name`.
- **Player colour**: the canonical in-game colour for a `color_id` (a fixed, small set).
- **Profile presentation**: how a profile's identity is shown — `alias`, `country`, avatar (referenced
  from the Steam CDN via the companion `avatarhash`), ratings, and the demoted numeric id.
- **Match presentation**: how a stored match is shown — civilisations, map, player colours, outcome,
  and rating movement — for the participants of one `game_id`.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A user can identify a match's civilisations, map, and outcome without reading any
  numeric identifier, for 100% of matches whose ids are covered by the shipped packs and mapping.
- **SC-002**: A profile shows the player's name and (when stored) country instead of a numeric id for
  100% of profiles that have `alias` stored.
- **SC-003**: 100% of game-asset packs present in the repository have a recorded source and permitted
  usage; a pack without that record is absent.
- **SC-004**: For the same profile, the profile and match views present the same categories of
  information a comparable third-party site shows for it — civilisation, map, player colour, outcome,
  and rating movement — with the sole documented exception of information this application does not
  hold (per-unit/building/resource detail, which requires replay parsing).
- **SC-005**: An identifier not covered by a pack or mapping renders as a readable label with zero
  broken or missing images across the profile and match views.
- **SC-006**: Every new or changed component has a Storybook story and passes visual regression in
  both light and dark theme.

## Assumptions

- The data enumerated in Context is present and current in feature 001's stored model; this feature
  reads it and does not re-derive or re-ingest it. Where a specific profile lacks a value (e.g.
  `1807091` showing no alias in the current UI), the fallback rules (FR-007, FR-010) apply rather
  than new ingestion.
- **Unit, building, and resource icons are out of scope.** They require per-match parsed replay data,
  which is a V2 capability (parsing, constitution I ordering); no such data exists in the phase-1
  model, so there is nothing to key those icons to. They re-enter scope when parsing does.
- The civilisation id→name mapping and the "unknown id shows as a number" discipline are owned by
  feature 002; this feature consumes that mapping and keys civilisation icons by the same ids rather
  than re-deriving names.
- Country flags are not game assets (they are standard national flags) and are not governed by the
  Microsoft Game Content Usage Rules; civilisation, map, unit and building imagery are.
- Player colours are a small fixed set defined by the game's canonical player colours; they are
  represented as design-system colour values rather than bitmap assets where possible.
- The specific community asset source(s) for civilisation icons and map minimap thumbnails (e.g. those
  documented in feature 002 — aoe2techtree, aoc-reference-data, aoe2-apis) and their individual
  licences are chosen and recorded during planning under the FR-011 gate; the spec fixes the
  requirement, not the source.
- The player avatar is not a game asset: it is the user's own Steam avatar, referenced from the Steam
  CDN and never copied into the repository. The FR-011 licence gate therefore does not apply to it;
  the companion provider that yields the hash is enrichment-only and degradable, so a missing avatar
  never blocks the view.
- This feature depends on constitution 5.0.0 (principle X) being in effect; it is stacked on that
  amendment's pull request.
