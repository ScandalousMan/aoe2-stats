# MatchRow and MatchDetailPanel

**Components**: `src/components/MatchRow/`, `src/components/MatchDetailPanel/`
**Feature**: 001, US3 — consumed by `apps/web/src/routes/matches.index.tsx` (T075) and
`apps/web/src/routes/matches.$gameId.tsx` (T076). **Extended by 003, US2** (§11) — consumed by
`apps/web/src/routes/players.$profileId.matches.tsx` (003 T331) for any player's history, and by the
same `matches.$gameId.tsx` route, widened (003 T331) to any match this service holds.
**Requirements**: FR-010, FR-011, FR-027, FR-028. SC-010. **§11 also carries 003's FR-007, FR-008,
FR-008a, FR-018, FR-019, FR-020, FR-021, FR-022. SC-003** — prefixed `003` throughout §11 to keep
them apart from 001's own numbers above, which share digits with different requirements in 003's own
numbering.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`,
`StatValue`. [`capture-state-badge.md`](./capture-state-badge.md) — `CaptureStateBadge`.
[`profile-summary.md`](./profile-summary.md) — the page header above both routes is a `ProfileSummary`
`compact` variant (§11's own `subject="other"` reading, [profile-summary.md](./profile-summary.md)
§11, when the profile viewed is not the caller's own); neither component below repeats identity
information it already shows.

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
├─ Map                  factual name, text only — no map thumbnail (constitution X)
├─ Civilisation         the caller's own civilisation, factual name, text only — no civ emblem
├─ RatingChange         StatValue/inline, signed
├─ Duration             "34 min" — never raw seconds
├─ When                 relative time, absolute time on hover/focus (title attribute or tooltip)
└─ CaptureStateBadge    context="compact" — see capture-state-badge.md

MatchDetailPanel
├─ Header
│  ├─ Map, leaderboard name, duration, played-on date/time
│  ├─ GameVersion                 raw patch string (e.g. "101.101") — 003 FR-018, §11.1
│  └─ CaptureStateBadge          context="detail"
├─ DownloadAction                Button/secondary — present only when capture_status = "stored"
├─ ParticipantsTable             FR-011: every participant, grouped by team
│  └─ TeamGroup ×n
│     └─ ParticipantRow ×n       alias, civilisation, result (§2a), rating change
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
work, out of scope here. What this section fixes is that the *absence* of that data must read as
absence, not as the specific, false fact "Loss."

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

Gaps in play: **DS-8** (tabular alignment for `RatingChange` rides on `font-mono`, same as
`profile-summary.md`). No new gap is introduced by either component; `CaptureStateBadge`'s own gap
register (none) is unaffected.

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
      remaining aliases appear only once the row is opened.
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
- **`text-secondary`, never `text-primary`.** A resolved name is `text-primary` (§2's "factual name,
  text only"); an unresolved one is deliberately one step down the same hierarchy a stale or
  unmeasured figure already sits at elsewhere in this system (`profile-summary.md`'s `FreshnessLine`,
  this file's own `text-secondary` labels) — a fact this service is confident in is never typeset
  identically to one it is not.
- **`font-mono`**, matching every other bare identifier in this system (DS-8: `ProfileId` in
  `profile-summary.md`, the games-played figure in `player-search.md`) — a name is prose, an id is
  data, and the two must not share a typeface here for the same reason a rating and a label do not.

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

No new colour, spacing or radius token. `UnresolvedIdentifier` (§11.2) reuses `text-secondary` and
`font-mono`, both already tabled in §6; `GameVersion` (§11.1) reuses `text-secondary` at the header's
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
      "Map ID `<n>`") in `text-secondary`/`font-mono`, visibly distinct from a resolved name in the
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
