# MatchRow and MatchDetailPanel

**Components**: `src/components/MatchRow/`, `src/components/MatchDetailPanel/`
**Feature**: 001, US3 — consumed by `apps/web/src/routes/matches.index.tsx` (T075) and
`apps/web/src/routes/matches.$gameId.tsx` (T076). **Extended by 003, US2** (§11) — consumed by
`apps/web/src/routes/players.$profileId.matches.tsx` (003 T331) for any player's history, and by the
same `matches.$gameId.tsx` route, widened (003 T331) to any match this service holds. **Extended by
004, US1** (§12) — game imagery, participant grouping and rating movement, across the same three
routes.
**Requirements**: FR-010, FR-011, FR-027, FR-028. SC-010. **§11 also carries 003's FR-007, FR-008,
FR-008a, FR-018, FR-019, FR-020, FR-021, FR-022. SC-003** — prefixed `003` throughout §11 to keep
them apart from 001's own numbers above, which share digits with different requirements in 003's own
numbering. **§12 carries 004's FR-001 to FR-006, FR-010, FR-013 and FR-016. SC-001, SC-005** —
prefixed `004` throughout §12, for the same reason.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`,
`StatValue`. [`capture-state-badge.md`](./capture-state-badge.md) — `CaptureStateBadge`.
[`profile-summary.md`](./profile-summary.md) — every list route (`matches.index.tsx` and, per §11.3,
`players.$profileId.matches.tsx`) carries a `ProfileSummary` `compact` variant page header (§11's own
`subject="other"` reading, [profile-summary.md](./profile-summary.md) §11, when the profile viewed is
not the caller's own). **The detail route (`matches.$gameId.tsx`) carries no such header** (003
T412): a game detail's subject is the match, not any one participant, so there is no profile for a
`ProfileSummary` to summarise — removed after shipping as the compact header's empty avatar square on
a page with no player to show one for. Neither component below repeats identity information a list
route's header already shows. **§12 additionally depends on**
[`civilisation-icon.md`](./civilisation-icon.md), [`map-thumbnail.md`](./map-thumbnail.md) and
[`player-colour-swatch.md`](./player-colour-swatch.md) — the three marks are specified in full there
and only _composed_ here — and on [`game-asset-tokens.md`](./game-asset-tokens.md) for the
player-colour and `icon` token families.

## 1. Purpose

`MatchRow`: let a user scan their recent matches and tell, for each one, what happened and whether
its replay is safe — without opening it. `MatchDetailPanel`: everything about one match, every
participant, and the one action a `stored` replay is for — downloading it.

## 2. Anatomy

```
MatchRow                                                       one per match, the whole row is a link
├─ Outcome              "Win" / "Loss" / "Unknown" as text, success/danger/neutral — never colour
│                       alone. "Unknown" whenever the result is not yet known (§2a)
├─ Opponent             1v1: the opponent's alias. Team game: primary opponent + "and N others"
│                       — SUPERSEDED by §12.3's Participants: both sides, each in their colour
├─ Map                  factual name, text only — no map thumbnail (constitution X)
│                       — SUPERSEDED by §12.2: 5.0.0 permits a licence-recorded thumbnail
├─ Civilisation         the caller's own civilisation, factual name, text only — no civ emblem
│                       — SUPERSEDED by §12.2: CivilisationIcon, mark + name
├─ RatingChange         StatValue/inline, signed
│                       — WIDENED by §12.4 to Rating: the absolute value and its signed change
├─ Duration             "34 min" — never raw seconds
├─ When                 relative time, absolute time on hover/focus (title attribute or tooltip)
└─ CaptureStateBadge    context="compact" — see capture-state-badge.md

MatchDetailPanel
├─ Header
│  ├─ Map, leaderboard name, duration, played-on date/time
│  │                             — Map WIDENED by §12.5 to MapThumbnail (lg) + name
│  ├─ GameVersion                 raw patch string (e.g. "101.101") — 003 FR-018, §11.1
│  └─ CaptureStateBadge          context="detail"
├─ DownloadAction                Button/secondary — present only when capture_status = "stored"
├─ ParticipantsTable             FR-011: every participant, grouped by team
│  └─ TeamGroup ×n               — gains a TeamResult marker in its heading (§12.3)
│     └─ ParticipantRow ×n       alias, civilisation, result (§2a), rating change
│                                — WIDENED by §12.5: colour swatch before the alias, civilisation
│                                  as mark + name, rating as value + signed change
└─ StatusRegion                  Callout ×0..1 — the detail failed to load, or nothing to show
```

An upload affordance for a `lost` capture is **not** part of this anatomy — it is
`UploadControl`, specified separately (T082, US4) and wired into this route only where no archive
exists (T084). `MatchDetailPanel` reserves no fixed slot for it here so the two specs do not
describe the same region twice; T084 places it below `DownloadAction`'s position when
`DownloadAction` itself is absent.

**IP note**: map names and civilisation names are factual names, set as text in our own typeface —
the same rule `profile-summary.md` states for leaderboard names. No map thumbnail, no civilisation
emblem, no in-game font, no portrait. Constitution X.

**Superseded in part by §12, and the sentence is left standing so the next reader finds why.**
Constitution X **5.0.0** now permits game assets needed to display game content — map, civilisation,
unit, building and resource icons, flags and player colours — to be copied into the repository and
served, on two anchors: strictly non-commercial, and the Microsoft "Game Content Usage Rules"
disclaimer in both the README and the site footer. Every pack carries a licence record
(`specs/004-visual-parity/contracts/asset-pack.md`), enforced by `scripts/checks/asset_packs.py`. So
the map thumbnail and the civilisation emblem are now permitted and are specified in §12. **The rest
of the note stands unchanged**: no in-game font, no portrait, no screenshot — nothing else has been
ruled on, and names remain factual text in our own typeface.

### 2a. The unknown outcome, never rendered as a loss (Amended 2026-08-29)

**A `result` this service has not yet recorded is not the same fact as a loss, and must never read
as one.** `match_players.result` is `null` for every row this system has written to date
(`apps/ingester/src/aoe2stats_ingester/discover.py`'s `upsert_match_player` inserts only
`(game_id, profile_id)`; no enrichment stage yet fills in a player's result). Before this amendment,
`formatOutcome` coerced anything that was not literally `"win"` — `null` included — to `"loss"`,
which meant an eight-player match with no known result anywhere rendered as eight losses: a
confident, false statement produced from an absence of information. This is the same failure
`spec.md`'s FR-020 already forbids for `Civilisation` and `Map` (§11.2's "a guess dressed as a fact
is worse than an admitted gap"), applied here to `result` instead of a name.

**`Outcome` (`MatchRow`) and the `ParticipantsTable` `Result` column (`MatchDetailPanel`) each carry
a third state, `"unknown"`, alongside `"win"` and `"loss"`.** Rendered as the literal word
**"Unknown"**, matching this file's own "Unknown map" / "Unknown civilisation" / "Unknown opponent"
wording elsewhere (`format.ts`) rather than inventing a different phrase for the same kind of gap.
Three properties distinguish it from a resolved outcome, the same discipline §11.2 already states
for an unresolved identifier:

- **Never `success` or `danger`.** Those two tokens assert a fact this service does not have; the
  unknown state is `text-secondary` — the same "one step down the hierarchy" §11.2 already uses for
  an unresolved identifier and `profile-summary.md`'s `FreshnessLine` use for a stale figure.
- **Not bold in the same way a resolved outcome is** — `font-semibold` is unchanged (a lighter weight
  here would itself be a second, quieter way of asserting confidence this service does not have, the
  opposite of the intended read); the colour step is what carries the distinction, not weight.
- **The word itself reads as a gap, not a result** — "Unknown" is neither "Win" nor "Loss" textually,
  so the distinction survives a screen reader, a greyscale conversion, or a colour-blind reading
  without the colour token doing any of the work alone (constitution VI).

**`MatchDetailPanel`'s `ParticipantsTable` renders the same three-state result, per participant, not
just per row.** A match with no consenting participant among this service's own users can still
carry every participant's result unknown — the eight-player case that motivated this amendment — and
each participant reads "Unknown" independently; nothing here collapses the row into a single
combined message, matching §11.4's "a match with no consenting participant still renders in full."

**This does not change when a result is unknown, only how it renders.** Filling the ingestion gap
`discover.py`'s own docstring names — a stage that resolves `result` after the fact — is separate
work, out of scope here. What this section fixes is that the _absence_ of that data must read as
absence, not as the specific, false fact "Loss." **004 fills that gap** (research.md D1: the columns
were declared and never written; T413/T415 project them from `matches.raw_payload`), so "Unknown"
stops being every row's state — and §2a stops being hypothetical, because it is now the render for
the matches that genuinely have no recorded result rather than for all of them.

## 3. Variants and sizes

Neither component has variants of its own; both take their variation entirely from the match data
and from `CaptureStateBadge`'s own tone (see `capture-state-badge.md`). Sizing is responsive, not an
independent axis (§7).

## 4. `Opponent` for team matches

FR-010 asks for "opponent"; a 2v2+ match has several. `MatchRow` names the first opposing-team
participant by alias and appends `"and N others"` where `N` is the remainder of every team that is
not the caller's own — never a bare count with no name, and never every alias crammed onto one row
(that is what `MatchDetailPanel`'s `ParticipantsTable` is for). `"and N others"` is a link to the
same match detail, not a tooltip: FR-011's "every participant" must be one click away from the row
that summarised them, never an information dead end.

**Superseded by §12.3.** `MatchRow` now names both sides, each participant beside their colour, and
`"and N others"` survives as the _overflow_ device rather than as the whole treatment of the opposing
team. The requirement this section exists to satisfy — never a bare count with no name, never an
information dead end — is carried forward verbatim in §12.3.

## 5. States

- **default** — as tabled in §2.
- **hover** — `MatchRow`: whole-row hover fill `surface-sunken` (the row is a single link; nothing
  inside it — including `CaptureStateBadge` — has its own hover, consistent with
  `capture-state-badge.md` §6). `DownloadAction`: per `Button`.
- **focus-visible** — `MatchRow`: standard ring on the row's own link wrapper, inset so it never
  crops the outcome text or a numeral. `DownloadAction`: per `Button`.
- **active** — `MatchRow`: per link; `DownloadAction`: per `Button`.
- **disabled** — `DownloadAction` has no disabled form: while `capture_status != "stored"` it is
  **absent**, not disabled, following `profile-summary.md`'s own rule for the primary profile's
  "Make primary" item — `CaptureStateBadge` already explains why in that case, and a greyed-out
  button repeating "you can't do this yet" next to a badge that already said so is noise.
- **loading**:
  - `MatchRow` list, before the first page arrives: 5 `Skeleton/block` rows at the row's own
    footprint (never fewer than what the viewport shows without scrolling). No `0`, no `–`, no
    partial row.
  - `MatchDetailPanel`, before the match loads: header fields as `Skeleton/text`,
    `CaptureStateBadge` as its own loading state (`capture-state-badge.md` §6),
    `ParticipantsTable` as 2 `Skeleton/block` rows per the smallest known team size (2, until the
    real count arrives).
  - `DownloadAction`, while the signed URL is being requested: `Button`'s own `loading` state,
    label "Preparing your download…" (per `shared-primitives.md`'s rule that a caller supplying no
    loading label is wrong — this one always supplies one).
- **error**:
  - `MatchRow` list failed to load: `Callout/danger`, "We could not load your match history", with a
    retry — replacing the list, never leaving skeletons pulsing (`Skeleton`'s own 10 s rule).
  - `MatchDetailPanel` failed to load (network failure, distinct from "this match does not exist" —
    see empty below): same shape, "We could not load this match", with a retry.
  - `DownloadAction` failed: the button returns to `default` and is pressable again
    (`shared-primitives.md`'s `Button` rule: "the button returns to default and to being pressable");
    a `Callout/danger` renders in `StatusRegion`, "The download link could not be created. Try
    again." A failed download must never be the state that makes retrying unreachable.
- **empty**:
  - `MatchRow` list, zero matches: `Callout/info` in place of the list, "No matches yet. Once you
    play, they will appear here." (spec.md US3 acceptance scenario 5 — "a clear empty state, not a
    broken or blank page"). The page header (`ProfileSummary/compact`) still renders above it: the
    user is real even if their history is not yet.
  - `MatchDetailPanel`, a `game_id` that does not resolve for the caller (unknown, or real but not
    theirs — `contracts/http-api.md`'s identical-`not_found` rule, FR-045): `Callout/danger` (this is
    a dead end, not an absence to wait out), "This match could not be found.", with a link back to
    the match list. Never a blank panel and never a hint that distinguishes "does not exist" from
    "not yours" (that distinction must not leak — FR-045). **Amended by 003, §11.4**: `GET /api/
matches/{game_id}` no longer has an ownership scope to leak (T327) — "no such match" is the sole
    remaining cause of this `404`, and the copy is kept verbatim because it was already truthful for
    that cause; the sentence above is left in place, rather than rewritten, so the next reader finds
    why it never distinguished a case that no longer exists, not only that it still does not.

## 6. Tokens used

Colour: `background` (page), `surface` (row/panel), `surface-raised` (`CaptureStateBadge` pill fill,
via that component), `surface-sunken` (row hover, skeleton fill), `border` (row/table rules),
`border-strong` (`DownloadAction`'s boundary, per `Button/secondary`), `text-primary` (aliases, map,
civilisation, a resolved outcome's text), `text-secondary` (labels, "When", duration, and the
unknown-outcome text, §2a — no new token), `success`/`danger` (a resolved outcome's text and
`RatingChange` sign — see `capture-state-badge.md` §5 for the badge's own use of these two plus
`warning`/`info`), `focus-ring`.

Typography: `mono` for `RatingChange` and any other figure compared vertically down the list (DS-8);
`sans` for every label, name and sentence. Sizes: row text `sm`; outcome `sm` `semibold`;
`RatingChange` `md` (`StatValue/inline`); panel heading `xl`; participant table figures `sm`.
Tracking `tight` on `RatingChange` only, per `StatValue`.

Radius: `lg` (row card at 375, panel), `full` (`CaptureStateBadge` pill, via that component). Motion:
`duration.fast` + `easing.standard` on row hover; **no motion on any figure** (`StatValue`'s own
rule) — `RatingChange` never counts up, the outcome never fades in.

Gaps in play: none. **DS-8 closed** (T531) — `RatingChange`'s tabular alignment now comes from
`type-numeric`'s `tabular-nums`, same as `profile-summary.md`. **DS-7 is closed** by 004's `icon`
family (`game-asset-tokens.md`), which is what §12's three marks size from.

## 7. Spacing

| Between                                                                   | Step      |
| ------------------------------------------------------------------------- | --------- |
| Page header (`ProfileSummary/compact`) to match list                      | `space-6` |
| Between `MatchRow` cards (375)                                            | `space-3` |
| `MatchRow` padding (375 card)                                             | `space-4` |
| `MatchRow` table row padding-block (1280)                                 | `space-3` |
| `MatchRow` table column gap (1280)                                        | `space-5` |
| Outcome to opponent                                                       | `space-2` |
| `CaptureStateBadge` from the rest of the row (375, wraps to its own line) | `space-2` |
| Panel header to `DownloadAction`                                          | `space-4` |
| `DownloadAction` to `ParticipantsTable`                                   | `space-6` |
| Between `TeamGroup`s                                                      | `space-5` |
| `ParticipantsTable` row padding-block                                     | `space-3` |

§12.7 adds the steps the three new marks need; nothing above changes.

## 8. Responsive

- **375** — `MatchRow` renders as a stacked full-width card: outcome + opponent on the first line,
  map / civilisation / duration wrapping onto a second line at `text-secondary`, `RatingChange`
  right-aligned on the first line, `CaptureStateBadge` on its own line beneath (its `SecondaryLine`
  wraps per `capture-state-badge.md` §7). `MatchDetailPanel`'s `ParticipantsTable` renders as one
  card per participant, grouped under a `TeamGroup` heading.
- **768** — `MatchRow` cards gain a second column (map/civilisation beside duration/when).
  `ParticipantsTable` stays card-based but two participants sit side by side within a `TeamGroup`.
- **1280** — `MatchRow` becomes a real `<table>`: columns _Result · Opponent · Map · Civilisation ·
  Change · Duration · When · Capture_. Figures right-aligned, `CaptureStateBadge` in the trailing
  column with its `SecondaryLine` beneath the pill rather than beside it (column width is bounded).
  `ParticipantsTable` becomes a real `<table>` per `TeamGroup`, ruled with `border`, no card shadows —
  the same reasoning `profile-summary.md` §8 gives for its own rating board.

**Do not render both layouts and hide one** — `profile-summary.md`'s own rule, restated here because
it is the same list-versus-table shape: one DOM, restructured at the breakpoint.

**§12.7 renames two of the 1280 columns** (_Opponent_ → _Players_, _Change_ → _Rating_) and adds the
imagery to the card layout; the structure, the breakpoints and the one-DOM rule are unchanged.

## 9. Accessibility

- `MatchRow`'s whole card/row is one `<a>` (never a `<div>` with a click handler); everything inside
  it — including `CaptureStateBadge` — is non-interactive text, so the row has exactly one focus
  stop, not one per field.
- The match list is a `<ul>`/`<li>` at 375/768 and a real `<table>` with `<caption>` ("Your recent
  matches") and `<th scope="col">` at 1280 — one DOM per §8, `role`/element switching with it, never
  duplicated.
- `MatchDetailPanel`'s `ParticipantsTable`: a real `<table>` per `TeamGroup`, with a visually hidden
  `<caption>` naming the team, `<th scope="col">` on every column and `<th scope="row">` on each
  participant's alias.
- Outcome ("Win"/"Loss"/"Unknown", §2a) and `RatingChange`'s sign are both text, never colour-only,
  matching `profile-summary.md`'s delta rule ("+12"/"−12", not a rotated arrow). "Unknown" is
  additionally distinct from either resolved word by its own wording, so a screen reader or a
  greyscale screenshot never has to rely on the colour step alone.
- `DownloadAction` triggers a same-tab navigation to the signed-URL redirect (FR-028); it is a real
  `<button>` that calls the download endpoint, not a bare `<a href>` to an unsigned URL — the URL is
  minted per click (FR-040's access-log write happens server-side on that request).
- `CaptureStateBadge` accessibility is entirely its own component's responsibility — see
  `capture-state-badge.md` §11; neither `MatchRow` nor `MatchDetailPanel` re-implements it.
- Every figure (duration, rating change) is selectable text, never an image or canvas —
  `profile-summary.md`'s rule extended here.
- 200% zoom and 320px logical width without horizontal scrolling; at 320px the desktop table layouts
  are not in play (§8), so no cell ever truncates.

## 10. Visual acceptance criteria

**List**

- [ ] At 1280 the match list renders as a ruled table with a visible capture column; at 375 it
      renders as stacked cards. Only one of the two is present in the DOM in a given screenshot.
- [ ] Every row shows a `CaptureStateBadge` reading one of exactly four labels: "Archived", "Still
      catchable", "Lost", "Needs review" — never "Safe" (see `capture-state-badge.md` §3).
- [ ] A team match's `Opponent` field never lists more than one alias plus "and N others" inline; the
      remaining aliases appear only once the row is opened. **Superseded by §12.8's first criterion**
      — the row now names both sides under a cap, and the overflow rule ("and N others", never a bare
      count) is what survives.
- [ ] The empty-history screenshot shows the page header still present, above an info callout — never
      a blank page.
- [ ] The loading screenshot's skeleton row count matches the loaded screenshot's row count at the
      same viewport, with no reflow between the two.
- [ ] A story seeded with `outcome: 'unknown'` renders the literal word "Unknown" in `text-secondary`
      — never "Win", never "Loss", and never the `success`/`danger` colour (§2a). A story seeded with
      every row unknown (the all-unresolved-result match) renders no row implying a win or a loss.

**Detail**

- [ ] `DownloadAction` is present in the `stored` story and absent — not disabled — in every other
      capture-status story, including "Needs review" (cross-checked against
      `capture-state-badge.md`'s equivalent criterion).
- [ ] Every participant seeded in a story appears in the rendered `ParticipantsTable`, grouped under
      the correct team heading, with no participant duplicated or dropped.
- [ ] The not-found story shows a single danger callout and a link back to the match list — no field
      on the page distinguishes "this match does not exist" from "this match is not yours".
- [ ] Converting either component's screenshot to greyscale leaves outcome, rating change and capture
      state all still legible from text alone — the unknown-outcome story's "Unknown" reads as
      distinct from "Win"/"Loss" by wording alone, with no colour to lean on (§2a).

---

## 11. Reading any match, and any player's history (003, US2 — extends §§1–10, does not replace them)

**The rule this section exists to keep true: the same two components, opened wider, never a second
presentation.** 003 FR-018/FR-021 remove `GET /api/matches/{game_id}`'s ownership scope (T327) and
FR-007/FR-008a make any player's history reachable through the identical row shape `GET /api/matches`
already returns (T328); FR-008 forbids "a second, divergent presentation of the same facts," mirroring
`profile-summary.md` §11's own opening rule. Every section above — anatomy, states, tokens, spacing,
responsive, accessibility — applies unchanged to both components; this section states only what
widening the audience and the age of a match introduces, and why.

### 11.1 What changes, and what governs it

`MatchDetailPanel` no longer requires the caller to have played in the match (T327): `GET /api/
matches/{game_id}` answers `200` for any match this service holds, to any signed-in caller. Three
consequences follow directly, none of them a new prop or a new code path:

1. **No row is ever visually marked as "you."** `ParticipantsTable`'s anatomy (§2) already carries no
   such marker; FR-021 requires the identical page whichever history it was reached from, and a
   caller-relative highlight would itself be a second presentation of the same match, the exact thing
   FR-008/FR-021 forbid. A caller who is not among the participants sees the same table a participant
   sees.
2. **`CaptureStateBadge` and `DownloadAction` keep meaning exactly one thing: the _caller's own_
   archived replay, when they have one (FR-022).** Nothing here changes — the pair is `None`/`None`
   whenever the caller has no active link to a profile in the match
   (`MatchesRepository.get_match_detail`'s own docstring: "simply carries no archival state of their
   own"), and §5's existing rule ("`DownloadAction` is absent, not disabled, while
   `capture_status != stored`") already produces the right screen: no badge, no button, nothing
   implying a download FR-026 never offers for someone else's point of view. This is not the
   per-participant download list every point of view eventually gets — that is a separate component,
   specified for US3 (not yet written).
3. **`GameVersion` joins the header** (§2, this task): `MatchDetail.patch` (FR-018's "game version")
   is raw text exactly as reported by the source — there is no version-to-name table the way there is
   for civilisations and leaderboards (`routers/matches.py`'s own note: "there is nothing to look up
   here"), so `GameVersion` is never subject to §11.2's unresolved treatment below. It renders as
   plain `text-secondary` text beside duration, the same weight as the header's other facts.

### 11.2 Unnamed identifiers read as unresolved, not guessed (FR-020)

`Civilisation` (participant row, §2) and `Map` (header, §2) each carry a name resolved by this
service's own reference data (`civilisation_name`, `leaderboard_name`) — and each can come back
`null` when a new game version introduces an id neither table has yet learned (FR-020, US2 acceptance
scenario 4, quickstart scenario 5.4). **A `null` name is never filled in with the raw id set as if it
were a name.** Doing so would read exactly as confidently as a resolved one, which is the failure
FR-020 exists to forbid — a guess dressed as a fact is worse than an admitted gap.

Instead, whenever `civ_name` (or `map_name`) is `null`, the field renders as an
**`UnresolvedIdentifier`**: the literal Relic id, prefixed with what it is an id _of_, carrying three
signals a resolved name never uses, none of them colour alone:

- **A label prefix that says "id," not a name** — `"Civilisation ID 87"` / `"Map ID 204"`, never the
  bare number and never the field's own label with nothing marking it unresolved.
- **`type-identifier`** (T531, research D7, FR-007) carries both remaining signals by contract:
  `text-secondary`, never `text-primary` — a resolved name is `text-primary` (§2's "factual name,
  text only"); an unresolved one is deliberately one step down the same hierarchy a stale or
  unmeasured figure already sits at elsewhere in this system (`profile-summary.md`'s `FreshnessLine`,
  this file's own `text-secondary` labels), a fact this service is confident in never typeset
  identically to one it is not — and the mono family, matching every other bare identifier in this
  system (`ProfileId` in `profile-summary.md`): a name is prose, an id is data, and the two must not
  share a typeface here for the same reason a rating and a label do not. The games-played figure in
  `player-search.md` is a measured count, not an identifier, and carries `type-numeric` instead
  (T531) — the two were never the same signal, only the same shared `font-mono` before the roles
  split.

No icon and no additional colour token: three signals (wording, colour step, typeface) already clear
constitution VI's "never colour alone" rule without adding a fourth channel to justify.

This is the one behaviour `Civilisation` and `Map` share that no other field in this file does — every
other field is either always present in the same treatment (`Outcome`, `RatingChange`, `Duration`) or
absent entirely when unknown (`Standing` in `player-search.md`, this file's own `Rank` empty state in
`profile-summary.md`). An unnamed identifier is neither: it is present, and it is a fact — just not the
fact a name would assert.

### 11.3 The third-party history list (FR-007, FR-008a)

`MatchRow`, unchanged in every prop and every visual rule from §§1–10, is the list
`players.$profileId.matches.tsx` (T331) renders for any player's history — the same component
`matches.index.tsx` already used for the caller's own, because `GET /api/players/{profile_id}/matches`
answers in the identical row shape `GET /api/matches` does (`contracts/http-api.md`, `match_row_json`
shared by both routes, T328's own docstring: "the two routes can never drift apart on the one shape").
There is no second list component to specify.

**Every field is already relative to the profile being viewed, not to the caller — a property of the
API this component inherits rather than one it implements.**
`MatchesRepository.list_matches(profile_id=...)` computes `Civilisation` and `Opponent` against
whichever `profile_id` was asked for; when that id is a third party's, `Civilisation` is _their_
civilisation and `Opponent` is _their_ opponents, exactly as it is the caller's own when the id is the
caller's. `MatchRow` needs no `perspective` prop to get this right, and must not be given one: adding a
client-side perspective would risk a page that renders one player's row as if seen from another's,
which is exactly the drift FR-021's "identical whichever history it was reached from" forbids for the
detail page and which this list must not reintroduce for the same reason.

**The one thing that does differ by page context is the words around the list, never the row.** The
list's `<caption>` (§9: `"Your recent matches"`) and the empty state's copy (§5: `"No matches yet.
Once you play, they will appear here."`) both presuppose the viewer is the subject. Reused for a third
party's page they would misstate whose matches these are, or promise the _caller_ something will
appear once _they_ play. The page passes the viewed profile's alias in, and the two fixed strings
become two, chosen by the same `subject: "self" | "other"` read `profile-summary.md` §11 already
established for the header above this list:

| String           | `subject="self"`                                        | `subject="other"`                                |
| ---------------- | ------------------------------------------------------- | ------------------------------------------------ |
| `<caption>`      | "Your recent matches"                                   | "`<alias>`'s recent matches"                     |
| Empty state body | "No matches yet. Once you play, they will appear here." | "`<alias>` has no matches in their history yet." |

Neither copy implies the caller played, was invited to play, or has any relationship to the player
being viewed beyond having opened their profile — the empty state is a fact about the player, stated
once, the same discipline `profile-summary.md` §11.2 already applies to its own reused-verbatim empty
case.

**`CaptureStateBadge` inside a third-party row shows that player's own archival state with this
service, exactly as `match_row_json` reports it — unmodified, the same "capture state travels intact"
rule §§1–10 already state for the caller's own list.** This is not a new disclosure this task
introduces: `GET /api/players/{profile_id}/matches` (T328) already answers with the identical field,
for any profile, before this component existed to render it. There is no `DownloadAction` on
`MatchRow` at any point (§2: it lives only on `MatchDetailPanel`, gated to the caller's own point of
view per §11.1) — a third party's badge is informational, never an offered action the caller could not
actually take.

### 11.4 States §5 did not need to name

**Many participants, still one anatomy.** `MatchDetailPanel`'s `ParticipantsTable` (§2:
`TeamGroup ×n` / `ParticipantRow ×n`) already generalises to any team count without a new variant — an
eight-player free-for-all is eight `TeamGroup`s of one, a 1v1 is two of one, a 4v4 is two of four.
Nothing in §§3, §7 or §8 is conditional on participant count; the only visual property this task adds
is §11.2's unresolved treatment, which can appear on any row regardless of how many there are.

**The not-found dead end has one cause left, not two (§5, amended).** §5's existing bullet for
`MatchDetailPanel`'s not-found state predates T327 and its own amendment note now states why: since
T327 removed the ownership scope, "not yours" is no longer a case `GET /api/matches/{game_id}` can
produce at all. The copy is unchanged — it was already correct for the one cause that remains.

**A match with no consenting participant at all still renders in full.** `spec.md`'s own edge case ("a
match page is opened for a match in which none of this service's users participated") is not a new
state: FR-019 already requires the whole page to render from stored match data alone, and §11.1's
point 1 already established no row assumes the caller played. This edge case is the same "default"
state as any other match, and needed no new work to already be correct.

### 11.5 Tokens, spacing, accessibility — the delta only

No new colour, spacing or radius token. `UnresolvedIdentifier` (§11.2) reuses `type-identifier`
(T531), whose `text-secondary` is already tabled in §6; `GameVersion` (§11.1) reuses `text-secondary` at the header's
existing label size. The third-party list's caption and empty-state copy (§11.3) carry no new token —
they are `sans`/`text-secondary`, matching every other instance of `<caption>` and `Callout/info` body
text already specified in §§6 and 9.

Accessibility: `UnresolvedIdentifier`'s label prefix ("Civilisation ID," "Map ID") is real text inside
the same table cell §9 already gives a `<th scope="row">`/`<td>` — it needs no `aria-label`, because
the visible words already say what the number is. The list's `<caption>` changes its text content per
§11.3's table but keeps §9's existing element and role (a visually hidden `<caption>` on the `<table>`
at 1280, the accessible list name at 375/768) — screen-reader users get the corrected subject the same
way sighted users do, from the same string.

### 11.6 Visual acceptance criteria (additional to §10)

- [ ] A story seeded with `civ_name: null` (or `map_name: null`) renders "Civilisation ID `<n>`" (or
      "Map ID `<n>`") in `type-identifier`, visibly distinct from a resolved name in the
      same story's other rows — confirmed by placing both in one frame.
- [ ] The eight-player story renders eight distinguishable `TeamGroup`s with no participant dropped or
      duplicated, and the 1v1 story renders two — both from the identical component, no layout branch
      visible between them beyond row count.
- [ ] `GameVersion` is present in every `MatchDetailPanel` header story, including the loading story's
      `Skeleton/text` placeholder for it (§5's existing header-loading rule, extended to this field).
- [ ] The `players.$profileId.matches.tsx` story shows the caption "`<alias>`'s recent matches" and,
      seeded empty, the third-party empty-state sentence — never the first-person "Your"/"you play"
      copy from the caller's own list, confirmed side by side with that story.
- [ ] No `MatchRow` or `MatchDetailPanel` story marks any single participant as "you" — a story seeded
      with the caller absent from the match renders identically, in every other respect, to one seeded
      with the caller present.
- [ ] Converting the unresolved-identifier story to greyscale still reads "Civilisation ID `<n>`" as
      distinct from a resolved name, because the distinguishing signal is the label and the typeface,
      never colour alone.

---

## 12. Game imagery, participant grouping and rating movement (004, US1 — extends §§1–11, does not replace them)

**Two things changed underneath these components, and neither is a redesign.** Constitution X 5.0.0
permits licence-recorded game assets in the repository, so the civilisation emblem and the minimap
§2's IP note forbade are now specified (§2's amendment note). And five per-participant columns that
were declared, read by three routers and **written by nobody** now carry values (research.md D1;
T413/T415 project them from `matches.raw_payload`, T420 caches colour from companion) — so
`civ_id`, `team_id`, `result`, `rating`, `rating_diff` and `color_id` are facts these components can
render rather than nulls they have to explain.

Everything in §§1–11 applies unchanged. This section states only what the imagery and the newly
populated columns introduce, and — where it changes an earlier rule — says so in §12.2 rather than
quietly.

### 12.1 Three rules, stated once, because otherwise each component decides them differently

These are the decisions `CivilisationIcon`, `MapThumbnail`, `PlayerColourSwatch`, `MatchRow` and
`MatchDetailPanel` would each otherwise make on their own, and five answers to one question is how a
list and a detail view start disagreeing about the same match.

**1. Colour is never the only carrier of meaning** (004 FR-004; README rule 4). Two consequences bind
every component in this file:

- **A `PlayerColourSwatch` always sits beside a player's name**, in the same line or the same table
  cell. The swatch renders nothing at all when it has no name to sit beside
  ([`player-colour-swatch.md`](./player-colour-swatch.md) §2a), so the rule is structural rather than
  a convention each call site has to remember.
- **The winning side is distinguished by a word, not by a colour.** §12.3's `TeamResult` marker reads
  "Won" / "Lost" / "Result unknown"; `success` and `danger` are reinforcement on top of the word,
  never the signal itself. No trophy glyph on its own, no green row fill, no coloured left rule
  standing alone. §2a's third neutral state is the same discipline applied per participant, and it
  extends here: **a group whose result nobody recorded reads as unknown, never as a defeat.**

**2. The direction of a rating change is legible without colour** (004 FR-005's explicit clause:
"with direction conveyed by more than colour alone"). The sign is a **character in the text** —
`+16`, `−15` — always rendered, never dropped, never replaced by a rotated arrow (the rule
`profile-summary.md` already states for its own delta), and never left to `success`/`danger` to
imply. §12.4 fixes the format down to which minus sign.

**3. The absent-asset state is the prop being `undefined`, and it renders the readable label alone**
(004 FR-010, SC-005). Not a placeholder image, not a silhouette, not a "?" tile, not an empty framed
box — **a placeholder is a broken image with better manners**: it takes the same space, teaches the
reader nothing, and defeats the only check FR-010 is testable by, which is that no request under
`/game-assets/` ever 404s. `packages/game-assets`' resolvers return `undefined` rather than a URL
precisely so that nothing is requested for an identifier no pack covers; the components pass that
`undefined` through and draw nothing where the mark would have been.

A corollary that belongs with them: **the design system never imports an image and never reaches into
`packages/game-assets`** (plan.md's Structure Decision). `apps/web` resolves `civilisationIcon()` /
`mapThumbnail()` and passes a URL — or `undefined` — as a prop. That is what keeps these components
asset-agnostic, their unit tests free of binary fixtures, and the degrade path a single, testable
value rather than a fetch that may or may not fail.

### 12.2 What §12 supersedes, and what it leaves standing

| Earlier text                                                                     | Status                                                                                                                                               |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| §2's IP note, "No map thumbnail, no civilisation emblem"                         | **Superseded** for those two marks only, by constitution X 5.0.0 and the pack licence records. "No in-game font, no portrait, no screenshot" stands. |
| §2's `Map` and `Civilisation` anatomy lines ("text only")                        | **Superseded** by §12.5 and §12.3: mark + name, the name never suppressed.                                                                           |
| §4's `Opponent` treatment                                                        | **Superseded** by §12.3's `Participants`. Its requirement — never a bare count with no name, never an information dead end — is carried forward.     |
| §2's `RatingChange` line                                                         | **Widened** by §12.4: the absolute rating joins the signed change. The no-motion and `mono` rules are unchanged.                                     |
| §8's 1280 column list                                                            | Two columns **renamed** (§12.7): _Opponent_ → _Players_, _Change_ → _Rating_. Structure, breakpoints and the one-DOM rule unchanged.                 |
| §10's "`Opponent` never lists more than one alias" criterion                     | **Superseded** by §12.8's first criterion.                                                                                                           |
| §2a's three-state outcome, §11.1's "no row is marked as you", §11.2, §5's states | **Unchanged, and load-bearing.** §12 adds imagery to them; it removes none of them.                                                                  |

### 12.3 Participants, grouped by side, each in their colour (004 FR-003, FR-004)

`MatchRow` gains a **`Participants`** part, replacing §4's single-opponent treatment. It shows who
played, on which side, and in which colour.

**Composition.** Each participant renders as `PlayerColourSwatch` (`xs`) immediately followed by
their alias, `space-2` apart, never wrapping apart (§12.7). Participants are grouped by `team_id`;
groups are separated by the word **"vs"** in `text-secondary` — a word, not a glyph, so it survives
greyscale and reads correctly aloud.

**Ordering.** The viewed profile's team comes first, then the remaining groups ascending by
`team_id`; inside a group, the viewed profile first, then the order the API returned. This is not a
caller-relative perspective and must not become one: §11.3 already established that every field in a
row is relative to _the profile whose history is being read_, not to whoever is signed in, so the
same row renders identically for every caller. **No participant is marked as "you"** — §11.1's rule
holds here too; position is the only distinction, and the row's own `Outcome` already speaks for the
viewed player.

**The cap, and the overflow.** A row is a summary; `MatchDetailPanel` is where every participant is
guaranteed to appear (FR-011).

| Shape                                           | What the row names                                                                                     |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Two groups (1v1, 2v2, 3v3, 4v4 …)               | Up to **three** participants per group, in order; a longer group appends `"and N others"`              |
| More than two groups (a free-for-all)           | No grouping and no "vs": the viewed profile's swatch and alias, then `"and N others"` for all the rest |
| One group (co-op, or a partially projected row) | The single group, same cap of three, no "vs"                                                           |

`"and N others"` keeps §4's meaning exactly: never a bare count with no name, and never a dead end —
**but it needs no link of its own**, because the whole row already is one link to the same match
detail (§9). That preserves §9's "exactly one focus stop per row" while satisfying §4's requirement
that the remaining aliases are one click away.

**The `TeamResult` marker.** Every group carries a word derived from its participants' `result`s. It
is the FR-004 winner signal, and it is text:

| The group's participants                                         | Marker                 | Token            |
| ---------------------------------------------------------------- | ---------------------- | ---------------- |
| every `result` is `win`                                          | **"Won"**              | `success`        |
| every `result` is `loss`                                         | **"Lost"**             | `danger`         |
| no participant has a recorded `result`                           | **"Result unknown"**   | `text-secondary` |
| mixed recorded results (should not occur; possible mid-backfill) | no group marker at all | —                |

"Result unknown" reuses §2a's own vocabulary rather than inventing a second phrase for the same gap,
and is never `success` or `danger` — a group nobody recorded a result for **must not read as the
losing side**. The colour tokens reinforce the word; converting the screenshot to greyscale must
leave all three states readable (§12.8).

In `MatchRow` the marker precedes its group's names. In `MatchDetailPanel` it joins the `TeamGroup`
heading — "Team 1 — Won" — and the group's visually hidden `<caption>`, so the same words reach a
screen reader (§9's existing caption rule, extended, not replaced).

**What the row deliberately does not show.** Per-participant civilisations, ratings and results are
**detail only**. A row that showed eight aliases, eight colours, eight emblems and eight ratings
would be a table pretending to be a row, and README rule 1 settles that trade: the numbers a user
scans (rating, duration, when) must not be pushed off the line by imagery. The row's own
`Civilisation` field remains the _viewed profile's_ civilisation (§11.3), now as mark + name.

### 12.4 Rating and its movement (004 FR-005, FR-006)

**Format.** The absolute rating, then the signed change in parentheses: `922 (+16)`, `921 (−15)`.
`mono`, tracking `tight`, right-aligned in the 1280 table so signs and digits line up down the column
(DS-8). `text-primary` for the absolute value; `success` / `danger` on the parenthetical only, as
reinforcement for a sign that is already a character.

**The minus is U+2212 MINUS SIGN (`−`), not a hyphen** — it is the glyph the existing
`TableRatingChange` already renders, it aligns with digits in a monospaced face, and a screen reader
says "minus" rather than swallowing it.

**Four cases an implementer would otherwise decide separately:**

| Data                                      | Renders                                          | Why                                                                                                                |
| ----------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `rating` and `rating_diff` both present   | `922 (+16)`                                      | the FR-005 case                                                                                                    |
| `rating_diff` is exactly `0`              | `922 (0)`, `text-secondary` on the parenthetical | there is no direction to convey; `+0` asserts a gain that did not happen                                           |
| `rating_diff` is `null`, `rating` present | `922`                                            | `null` means _not known_ — never `(+0)`, never `(—)`, never a `0` standing in (`contracts/http-api.md`'s own rule) |
| both `null`                               | the field is **absent**                          | §5's existing "absent when the match carries no rating change to report"; never a `–`, never a `0`                 |

(If a `rating_diff` ever arrives without a `rating` — the data model says it cannot, since the diff is
`null` whenever either side is missing — render the change alone, `+16`, never an empty parenthesis.)

**No motion, ever**: no count-up, no flash on change, nothing that delays reading a number
(`StatValue`'s own rule and README rule 1).

**FR-006's metadata** — ladder, duration, date — is already stored and already partly rendered.
Duration and When are unchanged. The **ladder name** joins the `Map` field as a second, `xs`
`text-secondary` line beneath the map name ("Arabia" / "1v1 Random Map") rather than becoming a ninth
column: it qualifies the match's context, it is the field a reader consults after the map rather than
alongside the numbers, and a ninth column at 1280 would narrow every figure column to buy a fact
nobody scans. At 375/768 it joins the existing meta line.

### 12.5 `MatchDetailPanel`, widened (004 FR-001, FR-002, FR-003, FR-004)

- **Header**: `MapThumbnail` at `lg` (`icon-3xl`, 96px) beside the map name, leaderboard name,
  duration, played-on date/time and `GameVersion` (§11.1). A `null` map name keeps §11.2's
  `UnresolvedIdentifier` treatment and shows **no** thumbnail — nothing is guessed from the mode, the
  ladder or a neighbouring match.
- **`ParticipantsTable`**, per `TeamGroup`, columns at 1280: **Player** (`PlayerColourSwatch` `sm`
  then the alias, together in the `<th scope="row">`), **Civilisation** (`CivilisationIcon` `lg`,
  mark + name, or §11.2's `UnresolvedIdentifier`), **Result** (§2a's three states, unchanged),
  **Rating** (§12.4's format, identical rules).
- The swatch lives **inside the Player cell**, not in a colour column of its own: a column would put
  the chip a column away from the name it describes and invite reading it as a standalone status
  ([`player-colour-swatch.md`](./player-colour-swatch.md) §2a).
- The `TeamGroup` heading carries §12.3's `TeamResult` marker, and its visually hidden `<caption>`
  carries the same words.
- Group ordering here is strictly ascending `team_id` — **not** viewer-relative, because §11.1's
  point 1 requires the identical page whichever history it was reached from.
- **This panel composes the three marks; it never re-implements one.** Two presentations of the same
  fact are exactly how the list and the detail view start disagreeing about a match (T431's own
  wording), and the components exist so there is one answer to "what does an uncovered civilisation
  look like".

### 12.6 States §5 and §11.4 did not need to name

**default / hover / focus-visible / active / disabled** — unchanged from §5. None of the three marks
is interactive, none takes a `tabindex`, and none has a hover of its own: the row still has **exactly
one focus stop**, and the row's hover fill is still the only hover in play. A mark that grew, glowed
or revealed a preview on hover would also be invisible to the static screenshots this project gates
on, which is a second reason not to have one.

**loading** — §5's counts are unchanged (5 skeleton rows in the list; 2 per team in the panel), but
the **footprint now includes the imagery**: the skeleton row's height matches the loaded row's height
at the same viewport, thumbnail included, so there is no reflow when the data arrives (§10's existing
no-reflow criterion, which now has more to be true about). Each mark's own skeleton shape is in its
spec; no mark renders a partial version of itself while waiting.

**error** — three new failure modes, and all three render as an _absence_, never as an error:

- a civilisation emblem fails to load → the name alone, identical to the uncovered case;
- a minimap fails to load → the name alone, frame included in the removal, identical to the uncovered
  case;
- `color_id` outside `1..8` → the neutral chip, identical to `null`.

None of them produces a callout, a tone change or a retry: the match is fully readable without the
picture, and telling the user that an image did not load asks them to act on something they cannot.
The list-level and panel-level error states of §5 are unchanged.

**empty** — §5's two empty states (zero matches, match not found) are unchanged. §12 adds one state
neither §5 nor §11.4 had to name, and it is the state **every production row is in until the backfill
runs** (data-model.md §6's first transition — "row exists, all NULL"):

> **A match whose participant columns are not yet projected still renders in full.** `Outcome` reads
> "Unknown" (§2a), `Civilisation` and `Rating` are absent per their own rules, and the `Participants`
> field is **omitted entirely** — never an empty "vs" with nothing on either side, never a row of
> neutral chips with no names. Map, ladder, duration, when and `CaptureStateBadge` render from the
> `matches` columns, which have always been populated. A row in this state is a legitimate resting
> state, not a broken one.

The three degrade cases quickstart scenario 5 walks — unknown civ id, unknown map name, `null`
`color_id` — are **not** empty states of these components. The row is complete; a picture is simply
absent, which is what §12.1's third rule is for.

### 12.7 Tokens, spacing, responsive, accessibility — the delta only

**Tokens.** No new token and no new gap. Via the three marks: `player-1` … `player-8` and their
`-contrast` pairs, `surface-sunken` (the not-recorded chip), `border-strong` (the chip's frame,
meaning-bearing, 3:1), `border` (the thumbnail's frame, decorative), `icon-xs` / `icon-sm` /
`icon-md` / `icon-lg` / `icon-2xl` / `icon-3xl`, `radius-sm` and `radius-md`. §6's own list is
otherwise unchanged; `success` / `danger` / `text-secondary` carry §12.3's marker and §12.4's sign
exactly as they already carry `Outcome` and `RatingChange`. Every contrast pair in play is already in
README's measured table and already asserted by `tokens/build-tokens.test.mjs`.

**Spacing** (added to §7; nothing there changes):

| Between                                              | Step      |
| ---------------------------------------------------- | --------- |
| Colour swatch to the alias it belongs to             | `space-2` |
| Between two swatch+alias pairs within a group        | `space-3` |
| `TeamResult` marker to its group                     | `space-2` |
| Group to the "vs" divider, and divider to next group | `space-3` |
| Civilisation mark to its name                        | `space-2` |
| Map thumbnail to its name (`sm`)                     | `space-2` |
| Map thumbnail to its name (`md` / `lg`)              | `space-3` |
| Map name to the ladder line beneath it               | `space-1` |

**Responsive.** §8's structure, breakpoints and one-DOM rule are unchanged.

- **375** — `MapThumbnail` `md` (64px) leads the card, map name and ladder beside it;
  `CivilisationIcon` `md`; the `Participants` line wraps between pairs (never between a chip and its
  alias) and, if it still overflows, the cap of §12.3 has already bounded it. `Rating` stays
  right-aligned on the first line.
- **768** — as §8, with the imagery at the same sizes.
- **1280** — columns become _Result · **Players** · Map · Civilisation · **Rating** · Duration · When ·
  Capture_. `MapThumbnail` drops to `sm` (32px) here so a row with a thumbnail and a row without one
  are the same height ([`map-thumbnail.md`](./map-thumbnail.md) §7); the Players column names at most
  two participants per side before its overflow text, because the column's width is bounded by the
  table rather than by the window — the same reasoning §8 already gives `CaptureStateBadge`'s
  trailing column.
- **320px / 200% zoom** — the desktop table is not in play (§8), the marks are rem-sized so they grow
  with the text, and no cell truncates. The `Participants` line wraps rather than ellipsising —
  `profile-summary.md`'s "figures never ellipsise" discipline, extended to a name that is beside a
  colour nobody can read aloud.

**Accessibility.** §9 is unchanged and the delta is small, because the marks were specified to add
nothing to it:

- Both images are `alt=""` (decorative): the visible name beside each one is the accessible name, so
  no fact is announced twice.
- The colour swatch carries its meaning as visually hidden text ("Colour: Blue" / "Colour: not
  recorded"), in reading order immediately before the alias — never an `aria-label` standing in for
  visible text (`capture-state-badge.md` §11's rule, honoured here).
- The `TeamResult` marker is real text in the group heading and in the group's `<caption>`; a screen
  reader reaches "Team 1 — Won" without needing the colour.
- The rating's sign is a character in the text node, so it is announced and it survives greyscale;
  the parenthetical never becomes an image, a canvas or an icon font.
- Nothing new is interactive, so no new touch target exists; the row's single link is unchanged and
  the 44px floor (`icon-xl`) applies only if a future call site makes a mark a control.

### 12.8 Visual acceptance criteria (additional to §10 and §11.6)

**Imagery and the three degrade stories** — these are what SC-005 reduces to.

- [ ] The 1v1 story and the eight-player story each show **every named participant with a colour chip
      immediately beside their alias**; no chip appears anywhere without a name in the same line or
      cell, and the row names at most three participants per side (two per side at 1280) with the
      remainder carried by "and N others" — never a bare count.
- [ ] The uncovered-civilisation story shows the civilisation **name alone**: no box, no silhouette,
      no "?" tile, no gap where the mark would be. Placed in one frame beside a covered row, the two
      names sit on the same baseline.
- [ ] The uncovered-map story shows the map **name alone, with no frame** — an empty bordered box is a
      failure of this criterion, not a pass.
- [ ] The `color_id: null` story shows the neutral chip beside every affected alias, with the aliases
      still aligned with the rows above and below, and **no** `danger` or `warning` treatment
      anywhere.
- [ ] Across all three degrade stories, in both themes: **zero broken or missing images**, and the
      browser network panel shows no request under `/game-assets/` returning 404 (SC-005). A 404 there
      is a contract defect in the resolver, not a missing file (quickstart scenario 5).
- [ ] The 1280 table story shows rows with and without a map thumbnail at the **same row height**.

**Outcome, colour and the winning side**

- [ ] Every `TeamGroup`, in both components, carries one of exactly three words — "Won", "Lost",
      "Result unknown" — or no marker at all (the mixed case). A group with no recorded result reads
      "Result unknown" and is **visibly not** the same treatment as "Lost", in the same frame.
- [ ] Converting any match story to **greyscale** leaves: the winning side identifiable (the word),
      the rating direction identifiable (the sign), the outcome identifiable (§2a's three words), and
      every participant identifiable (their alias). Only the chips become indistinguishable — which is
      the point: nothing was riding on colour alone.
- [ ] No story renders a green fill, a red fill or a coloured left rule as the sole marker of the
      winning side.

**Rating**

- [ ] A story seeded `rating: 922, rating_diff: 16` renders `922 (+16)`; one seeded `-15` renders
      `921 (−15)` with the U+2212 minus; one seeded `0` renders `(0)` with no sign; one seeded
      `rating_diff: null` renders `922` with no parenthesis; one seeded both null renders no rating
      field at all — never a `–` and never a `0`.
- [ ] At 1280, the Rating column's signs and digits align vertically down the column in a story with
      mixed positive, negative and zero values.
- [ ] No rating animates on entry in any story (compare the first and second frames of the loading →
      loaded transition).

**Composition and states**

- [ ] The un-projected-row story (every participant column NULL) renders map, ladder, duration, when
      and the capture badge, with `Outcome` reading "Unknown", **no** `Participants` field, and no
      empty "vs" — and it is visibly not an error state.
- [ ] `MatchRow` and `MatchDetailPanel` stories seeded from the same match render the same
      civilisation mark, the same colours and the same winner — placed side by side in one frame, the
      two views agree on every fact they both show.
- [ ] The loading story and the loaded story at the same viewport overlay with no reflow, thumbnail
      footprint included.
- [ ] Every story exists in both light and dark theme, and no mark is tinted, filtered or otherwise
      theme-adjusted between the two (the chips and the pack images are identical in both).
