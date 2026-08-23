# MatchRow and MatchDetailPanel

**Components**: `src/components/MatchRow/`, `src/components/MatchDetailPanel/`
**Feature**: 001, US3 — consumed by `apps/web/src/routes/matches.index.tsx` (T075) and
`apps/web/src/routes/matches.$gameId.tsx` (T076)
**Requirements**: FR-010, FR-011, FR-027, FR-028. SC-010.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`,
`StatValue`. [`capture-state-badge.md`](./capture-state-badge.md) — `CaptureStateBadge`.
[`profile-summary.md`](./profile-summary.md) — the page header above both routes is a `ProfileSummary`
`compact` variant; neither component below repeats identity information it already shows.

## 1. Purpose

`MatchRow`: let a user scan their recent matches and tell, for each one, what happened and whether
its replay is safe — without opening it. `MatchDetailPanel`: everything about one match, every
participant, and the one action a `stored` replay is for — downloading it.

## 2. Anatomy

```
MatchRow                                                       one per match, the whole row is a link
├─ Outcome              "Win" / "Loss" as text, success/danger coloured — never colour alone
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
│  └─ CaptureStateBadge          context="detail"
├─ DownloadAction                Button/secondary — present only when capture_status = "stored"
├─ ParticipantsTable             FR-011: every participant, grouped by team
│  └─ TeamGroup ×n
│     └─ ParticipantRow ×n       alias, civilisation, result, rating change
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
    "not yours" (that distinction must not leak — FR-045).

## 6. Tokens used

Colour: `background` (page), `surface` (row/panel), `surface-raised` (`CaptureStateBadge` pill fill,
via that component), `surface-sunken` (row hover, skeleton fill), `border` (row/table rules),
`border-strong` (`DownloadAction`'s boundary, per `Button/secondary`), `text-primary` (aliases, map,
civilisation, outcome text), `text-secondary` (labels, "When", duration), `success`/`danger`
(outcome text and `RatingChange` sign — see `capture-state-badge.md` §5 for the badge's own use of
these two plus `warning`/`info`), `focus-ring`.

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
- Outcome ("Win"/"Loss") and `RatingChange`'s sign are both text, never colour-only, matching
  `profile-summary.md`'s delta rule ("+12"/"−12", not a rotated arrow).
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

**Detail**

- [ ] `DownloadAction` is present in the `stored` story and absent — not disabled — in every other
      capture-status story, including "Needs review" (cross-checked against
      `capture-state-badge.md`'s equivalent criterion).
- [ ] Every participant seeded in a story appears in the rendered `ParticipantsTable`, grouped under
      the correct team heading, with no participant duplicated or dropped.
- [ ] The not-found story shows a single danger callout and a link back to the match list — no field
      on the page distinguishes "this match does not exist" from "this match is not yours".
- [ ] Converting either component's screenshot to greyscale leaves outcome, rating change and capture
      state all still legible from text alone.
