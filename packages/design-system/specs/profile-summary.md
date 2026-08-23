# ProfileSummary

**Component**: `src/components/ProfileSummary/`
**Feature**: 001, US1 — consumed by `apps/web/src/routes/dashboard.tsx` and
`apps/web/src/features/profile/` (T037). **Extended by 003, US1** (§11) — consumed by
`apps/web/src/routes/players.$profileId.tsx` (003 T322), where it presents a profile that is not the
signed-in user's own.
**Requirements**: FR-008 (rating, rank, win/loss per leaderboard), FR-043 (one primary, others
reachable), FR-045 (never reveal that two linked accounts are one person), FR-004 (unlink trigger),
FR-007. SC-004. **§11 also carries 003's FR-006, FR-008, FR-008a, FR-009, FR-010, FR-013, FR-014** —
prefixed `003` throughout this file to keep them apart from 001's own FR-008/FR-004/FR-007/FR-045
above, which share numbers with different requirements in 003's own numbering.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `StatValue`, `Menu`, `Badge`,
`Button`, `Callout`, `Skeleton`. §11 also depends on
[`player-search.md`](./player-search.md)'s `PlayerSearchResult` shape for `alias_observed_at`.

## 1. Purpose

Show who the user is on the leaderboards — rating, rank and win/loss on every board they play — and
make their other linked profiles reachable in one gesture, without ever letting anyone else see that
those profiles belong to the same person.

## 2. Anatomy

```
ProfileSummary
├─ IdentityBar
│  ├─ ProfileSwitcher        Menu/selection. Trigger shows the viewed profile's alias as TEXT
│  ├─ CountryLabel           country name in text; a flag glyph may accompany it, never replace it
│  ├─ ProfileId              font-mono, xs, text-secondary — the identifier support will ask for
│  └─ ProfileActions         Button/ghost "Manage" → primary selection, unlink (FR-004)
├─ NonPrimaryBanner          Callout/info, present only while viewing a non-primary profile
├─ RatingBoard               one entry per leaderboard the profile has PLAYED (FR-008)
│  └─ RatingEntry ×n
│     ├─ LeaderboardName
│     ├─ Rating              StatValue/hero
│     ├─ RatingDelta         signed, since the previous snapshot
│     ├─ Rank                StatValue/compact
│     ├─ Record              wins–losses, as text, with a proportion bar
│     ├─ WinRate             StatValue/compact
│     ├─ Streak              e.g. "W3" / "L2"
│     └─ HighestRating       StatValue/compact, secondary
├─ FreshnessLine             when these figures were measured, and a retry
└─ StatusRegion              Callout ×0..1 — refresh failed, or nothing to show
```

Leaderboards the profile has never played are **absent**, not present-and-empty. FR-008 says "for
each leaderboard they have played"; a grid of em dashes for boards the user does not touch is noise
in a tool whose job is fast reading.

**IP note**: leaderboard names are factual names, set as text in our own typeface. No in-game font,
no board icon, no civilisation emblem, no map thumbnail. Country flags, if used at all, come from a
free-licensed set whose licence is recorded here before first use, and are decorative
(`aria-hidden`) beside the country name in text. Constitution X.

## 3. Variants and sizes

| Variant   | When                                           | Shape                                                                                                                                                  |
| --------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `board`   | dashboard header, the default                  | Full anatomy                                                                                                                                           |
| `compact` | page headers on match history and match detail | `IdentityBar` plus the primary leaderboard's rating and rank only, on one row. The switcher stays: FR-043's "reachable" does not stop at the dashboard |

Sizes are not an independent axis; the responsive layout in §8 drives density.

## 4. The multi-profile rules (FR-043 and FR-045)

These are product law, not styling, and they are the reason this component is specified rather than
assembled.

**Exactly one profile is primary.** The `Badge/accent` reading "Primary" appears on exactly one
menu item. Making another primary is an explicit action ("Make primary"), never a side effect of
viewing one.

**Viewing is not the same as promoting.** Selecting a profile in the switcher changes what this page
shows for the session; it writes nothing. While a non-primary profile is being viewed,
`NonPrimaryBanner` renders: _"You are viewing a profile that is not your primary one."_ with a
"Make primary" action and a "Back to <alias>" action. Without that banner a user cannot tell whether
they changed a setting or only a view, and FR-043's single primary becomes unreadable from the
screen.

**The switcher is reachable, not hidden** (FR-043). Its trigger displays the current alias as text
with a chevron. It is never an icon-only "⋯" button, never inside an overflow menu, never below the
fold on the dashboard, and it renders even when only one profile is linked — with that profile and a
"Link another Steam account" item, so the route to FR-007 exists before the second account does.

**Nothing links two profiles anywhere but here** (FR-045):

- The switcher is populated only from the authenticated `/api/me` payload. Unauthenticated, it
  renders nothing at all — not a disabled trigger, which would itself disclose that a set exists.
- No shared avatar, no "also known as", no "alt account", no visual pairing, no adjacency of two
  aliases anywhere outside the switcher's own popover.
- No cross-profile aggregate appears on anything addressed by a profile id: no combined rating, no
  combined record, no combined match count, no "total archived across your accounts" on a profile
  page. Cross-profile totals are permitted only on the owner's own account pages (quota, export,
  privacy), labelled as covering all of their linked accounts.
- Nothing derived from the set leaks into a shareable surface: page `<title>`, `<meta>` tags, Open
  Graph images, URLs, breadcrumb text and copy-link affordances mention the viewed profile only.
- No third-party "linked profiles" data is displayed, ever, even if a provider returns it. FR-045
  and T041 both hold this line; the component treats such a field as if it did not exist.

Players keep alternate accounts separate on purpose. A design that quietly outs them is a serious
defect even though it renders correctly.

## 5. States

**default** — identity bar, one `RatingEntry` per played leaderboard, freshness line. Ratings in
`font-mono`, the largest type in the component.

**hover** — switcher trigger and menu items per `Menu`. A `RatingEntry` is **not** interactive in
this feature (rating history is a later route) and therefore has no hover affordance: a row that
lights up under the cursor and does nothing when clicked is a promise the product does not keep.

**focus-visible** — standard ring on the trigger, on menu items, and on the ghost actions. The ring
never crops a numeral: rings on numeric rows are inset.

**active** — per `Button` and `Menu`.

**disabled** — the primary profile's own "Make primary" item is **absent**, not disabled: the
`Badge` already says why. While a primary change is in flight, every menu item is `aria-disabled`
and the target item shows the `Menu` loading state. The unlink action is disabled only while an
unlink is in flight.

**loading** — `IdentityBar` shows a `Skeleton/text` at the alias footprint; `RatingBoard` shows
`Skeleton` entries — one per leaderboard already known from cache, otherwise three. Per `StatValue`,
**no `0`, no `–`, no placeholder numeral ever renders in place of a figure that has not arrived.**
Do not paint before 200 ms. After 10 s, fall through to the error state.

**error** — two cases, and the difference is the whole point of a stats tool:

1. _Refresh failed, previous figures known_: the last known values render at full contrast, the
   `FreshnessLine` states when they were measured in relative and absolute time, and a
   `Callout/warning` in `StatusRegion` says "These figures could not be refreshed" with a "Try
   again" action. The board is never blanked to punish a failed request. Stale and labelled beats
   blank; blank beats wrong.
2. _Refresh failed, nothing known_: `Callout/danger`, "We could not load your ratings", with a
   retry. No skeleton left pulsing, no zeros.

**empty** — three, each distinct and each explanatory:

1. _Profile has played no leaderboard_: `Callout/info` — "No leaderboard has a rating for this
   profile yet. Ratings appear after your first ranked match." The identity bar still renders: the
   user is real even if their record is not.
2. _A played leaderboard with a rating but no rank yet_ (provisional): the `Rank` `StatValue` shows
   its empty state — a secondary-colour em dash — with the secondary line "Not ranked yet". The
   rating still renders; a missing rank never suppresses a known rating.
3. _One linked profile only_: not an empty state of the board but of the switcher — see §4. The
   trigger renders normally.

## 6. Tokens used

Colour: `background`, `surface` (component), `surface-raised` (rating entries and menu surface),
`surface-sunken` (proportion-bar track, disabled fills), `border` (entry boundaries, table rules),
`border-strong` (interactive boundaries), `text-primary` (aliases, ratings, ranks, records),
`text-secondary` (leaderboard names, labels, profile id, freshness line), `success` and `danger`
(win/loss bar, positive and negative deltas), `accent` / `accent-active` (the "Primary" badge label
— see `Badge`), `info` / `warning` (callouts), `focus-ring`, `overlay` (mobile switcher sheet).

Typography: family `mono` for every figure compared vertically — rating, rank, wins, losses, win
rate, delta — and `sans` for labels and prose. `display` on nothing here: figures are the hierarchy
and a decorative serif competing with them is exactly the trade this product refuses. Sizes —
alias `xl`; rating `3xl` (`2xl` below `md`); rank, win rate, streak `lg`; leaderboard name `sm` with
tracking `wide`; record `sm`; profile id, freshness, highest rating `xs`. Weights — `semibold` on
figures and the alias, `normal` on labels. Tracking `tight` on figures.

Radius `lg` (rating entries, menu), `md` (buttons), `full` (badge, proportion bar), `sm` (skeleton).
Elevation `none` on rating entries — they are separated by `border`, not by shadow, because a grid
of shadowed cards reads as slower than a ruled table — `overlay` on the switcher popover only.
Motion `duration.fast` + `easing.standard` on interactive transitions; `duration.fast` +
`easing.decelerate` on the switcher opening. **No motion on any figure**: no count-up, no
odometer, no entrance fade. Numbers are for reading, not for arriving.

Gaps in play: **DS-4** (focus ring), **DS-5** (the layout change at `lg`), **DS-8** (tabular
alignment currently rides on `font-mono` being monospaced — this component is the reason that gap
matters).

## 7. Spacing

| Between                                           | Step                                      |
| ------------------------------------------------- | ----------------------------------------- |
| Component padding                                 | `space-4` below `md`, `space-6` from `md` |
| Switcher trigger to country label                 | `space-3`                                 |
| Alias line to profile id                          | `space-1`                                 |
| Identity bar to non-primary banner                | `space-4`                                 |
| Identity bar (or banner) to rating board          | `space-6`                                 |
| Between rating entries (card layout)              | `space-4`                                 |
| Rating entry padding                              | `space-4`                                 |
| Leaderboard name to rating                        | `space-1`                                 |
| Rating to delta                                   | `space-2`                                 |
| Rating to the rank/record row                     | `space-3`                                 |
| Between rank, record, win rate, streak on one row | `space-5`                                 |
| Record text to proportion bar                     | `space-2`                                 |
| Rating board to freshness line                    | `space-4`                                 |
| Table row padding-block (desktop)                 | `space-3`                                 |
| Table column gap (desktop)                        | `space-6`                                 |

## 8. Responsive

- **375** — one card per leaderboard, full width, stacked at `space-4`. Within a card: leaderboard
  name, then rating at `2xl` with its delta on the same line, then rank / record / win rate / streak
  wrapping onto at most two rows. The switcher opens as a bottom sheet (`Menu`). Identity bar
  stacks: switcher trigger, then country and profile id on one line.
- **768** — two cards per row. Identity bar on one row, actions right-aligned.
- **1280** — the rating board becomes a real `<table>`: one row per leaderboard, columns
  _Leaderboard · Rating · Change · Rank · Record · Win rate · Streak · Best_. Figures
  right-aligned, labels left-aligned, ruled with `border` between rows and no shadow. At desktop
  density a table is read faster than cards, and comparing four boards is exactly what the user
  came for.

**Do not render both layouts and hide one.** Duplicated content breaks screen-reader output, doubles
the accessible names Playwright counts, and lets the two drift. One DOM, restructured at the `lg`
breakpoint.

## 9. Accessibility

- `IdentityBar` and `RatingBoard` sit in a `<section aria-labelledby>` headed by the profile alias
  (`<h2>`).
- Card layout: each `RatingEntry` is an `<article>` headed by the leaderboard name (`<h3>`), with
  the figures in a `<dl>` so each label is programmatically tied to its value.
- Table layout: a real `<table>` with a visually hidden `<caption>` ("Ratings for <alias>"),
  `<th scope="col">` on every column and `<th scope="row">` on the leaderboard name.
- `ProfileSwitcher` follows `Menu`: `aria-haspopup="menu"`, `aria-expanded`,
  `role="menuitemradio"` with `aria-checked` on the viewed profile, arrow-key roving, Escape closes
  and returns focus to the trigger. Items are ≥ 44px tall. The trigger's accessible name includes
  the word "profile" so it is not announced as a bare alias.
- The "Primary" state is carried by the badge's **text**, never by colour or position alone.
- Deltas carry a sign character in the accessible name ("+12", "−8"), not a rotated arrow.
  Wins/losses are printed as text ("142 W · 118 L") beside the proportion bar; the bar is
  `aria-hidden` and adds nothing that is not already readable.
- The proportion bar's fills (`success`, `danger`) meet 3:1 against `surface-sunken`; the bar is
  never the only place the record appears.
- `StatusRegion`: `role="status"` for info and warning, `role="alert"` for danger. Focus is not
  moved: this component updates in place while the user is reading.
- Every figure is selectable text, never an image or a canvas — a rating a user cannot copy is a
  rating they will retype by hand.
- Contrast per the README table. `accent` is never used for a figure in the light theme: figures are
  `text-primary`, and `accent` stays reserved for the badge label.
- 200% zoom and 320px logical width without horizontal scrolling; at 320px the desktop table is not
  in play, so no figure is ever truncated or ellipsised. Figures never ellipsise at any viewport.

## 10. Visual acceptance criteria

**Identity and the switcher**

- [ ] The switcher trigger shows the viewed profile's alias as readable text plus a chevron — not an
      icon-only or "⋯" control — and is visible without scrolling at 375, 768 and 1280.
- [ ] The open switcher shows exactly one "Primary" badge across all items.
- [ ] Each switcher item is at least 44px tall; at 375 the switcher is a full-width bottom sheet.
- [ ] The open switcher contains a "Link another Steam account" item, including in the
      single-profile screenshot.
- [ ] With the switcher closed, no second alias appears anywhere in the frame.
- [ ] In the unauthenticated story, no switcher trigger is rendered at all.
- [ ] While a non-primary profile is viewed, an info banner saying so is visible above the ratings.

**Numbers**

- [ ] Ratings are the largest text in the component and are set in the monospaced family.
- [ ] Stacked ratings, ranks and records align digit-for-digit vertically in the same screenshot.
- [ ] No gradient, texture, parchment grain, glow or border passes behind or across any figure.
- [ ] Every delta shows an explicit + or − character.
- [ ] The win/loss record is legible as text, not only as a coloured bar; converting the screenshot
      to greyscale leaves every win/loss and every delta still readable.
- [ ] No leaderboard the profile has not played appears in the frame.

**States**

- [ ] Loading: skeletons match the loaded footprint (overlaying the two screenshots shows no
      reflow), and no `0`, `–` or placeholder numeral appears anywhere.
- [ ] Stale/refresh-failed: the previous figures are still visible at full contrast, a warning
      callout is present, and a "Try again" button is enabled.
- [ ] Never-loaded error: a danger callout with a retry, no pulsing skeleton, no zeros.
- [ ] Empty (no rated leaderboard): the identity bar still renders, and an info callout explains
      when ratings will appear; the frame is not blank.
- [ ] Provisional rank: a secondary-colour em dash with "Not ranked yet", while the rating beside it
      still shows its real value.

**Layout and craft**

- [ ] At 1280 the ratings render as a ruled table with right-aligned figures, no card shadows.
- [ ] At 375 the ratings render as stacked full-width cards, one per leaderboard.
- [ ] Only one of those two layouts is present in the DOM at a time.
- [ ] Focus ring visible and unclipped on the switcher trigger and on the focused menu item, in both
      themes.
- [ ] No game artwork, board icon, civilisation emblem, map thumbnail or in-game font in the frame.

---

## 11. Viewing a third party (003, FR-008 and FR-008a — extends §§1–10, does not replace them)

**The rule this section exists to keep true: one component, two subjects.** 003 FR-008 forbids "a
second, divergent presentation of the same facts" — a third party's profile is `ProfileSummary`
rendering someone who is not the viewer, not a second component that happens to look similar. Every
section above (anatomy, tokens, spacing, responsive, accessibility) applies unchanged; this section
states only the differences a non-owning viewer introduces, and why each one exists.

### 11.1 What is different, and what governs it

`ProfileSummary` takes a new input, `subject: "self" | "other"`, alongside the profile data it already
takes. `subject: "other"` changes exactly four things:

1. **No `ProfileSwitcher`, ever** (003 FR-009, restating 001 FR-045 for a viewer who is not the owner).
   §4's switcher exists to move between _the signed-in user's own_ linked profiles; showing it while
   viewing someone else would either be empty and pointless or — if it somehow listed the viewed
   player's own linked accounts — the exact account-linkage disclosure 001 FR-045 and 003 FR-009 both
   forbid. `IdentityBar` therefore renders the alias as static text, not a `Menu` trigger, when
   `subject="other"`.
2. **No `NonPrimaryBanner`, no `ProfileActions` "Manage"/unlink.** Both are about the viewer's own
   account state (§4, §2) and have no meaning applied to someone else's profile; they are absent, not
   disabled, following the file's own rule for controls that do not apply (§5 "disabled").
3. **A `FavouriteToggle` action appears in `IdentityBar`**, replacing `ProfileActions`' position (003
   FR-013): a `Button/ghost` reading "Add to favourites" / "Remove from favourites" depending on
   current state, icon-plus-text (never icon-only, per `shared-primitives.md`'s `Button` rule). Absent
   entirely when `subject="self"` — a user cannot favourite their own profile, and the API gives this
   component no route to attempt it.
4. **`AliasFreshnessNote` appears beneath the alias**, reading the profile's `alias_observed_at`
   (`contracts/http-api.md`'s `GET /api/players/{profile_id}`): _"Last seen as <alias> on <date>."_ —
   present only when `subject="other"`. This is spec.md's own edge case ("a searched player has since
   changed their in-game alias… results may be stale") made honest rather than silent: the signed-in
   user's own alias is never stale to them the way a third party's can be, so `subject="self"` never
   shows it.

**Everything else is identical by construction, not by coincidence.** `RatingBoard`, `FreshnessLine`,
every `StatValue`, every empty and error state in §5, the responsive table transform in §8 and every
token in §6 are the same component, the same props, the same DOM shape — a third party's profile is
never rendered by a second code path, which is the whole of what 003 FR-008 asks for.

### 11.2 Two states §5 did not need to name, because a third party introduces them

**empty (fourth case) — a profile 003 US1 scenario 5 describes: searched, never played a ranked
ladder.** Identical to §5's empty case 1 ("Profile has played no leaderboard"), reused verbatim — the
copy does not change based on whose profile it is, because the fact stated ("no leaderboard has a
rating yet") is true regardless of who is looking.

**error (new case) — the profile does not resolve at all (`404`).** Neither `IdentityBar` nor
`RatingBoard` render; the whole component collapses to a single `Callout/danger`: _"This player could
not be found."_ with no further detail and a link back to search. 003's route contract answers `404`
identically whether the profile is genuinely unknown to both the source and this service — there is no
third case to distinguish, since FR-004c (a hidden-profile signal) was retired on measurement
(`docs/data-sources.md` §3, T301a) — so this component has, correctly, nothing more specific to say.
This mirrors `match-history.md` §5's identical `not_found` rule for `MatchDetailPanel`, applied here to
a profile instead of a match, for the same reason: a single indistinguishable dead end is what the
contract actually provides, and inventing a more specific message would assert a distinction the API
does not make.

### 11.3 Tokens, spacing, accessibility — the delta only

`FavouriteToggle` uses `Button/ghost` exactly as specified in `shared-primitives.md` — no new token.
`AliasFreshnessNote` uses `text-secondary` at `xs`, the same pairing `FreshnessLine` already uses one
row down, spaced `space-1` below the alias line. The 404 `Callout` uses `danger`, matching every other
not-found state in this system (`match-history.md` §5). No new token, no new gap.

Accessibility: `IdentityBar`'s static alias (no switcher) is a plain `<h2>`, exactly as §9 already
specifies for the section heading — `subject="other"` removes the `Menu` semantics `ProfileSwitcher`
would otherwise add, and adds nothing in their place. `FavouriteToggle` is a real `<button>` with
`aria-pressed` reflecting favourited state, label text changing with it (never an icon-only star,
`shared-primitives.md`'s `Button` rule). The 404 `Callout` gets `role="alert"` per `Callout`'s own
rule.

### 11.4 Visual acceptance criteria (additional to §10)

- [ ] The `subject="other"` story shows no `ProfileSwitcher` trigger anywhere in the frame, in either
      theme.
- [ ] The `subject="other"` story shows a `FavouriteToggle` in `IdentityBar`; the `subject="self"`
      story does not, in the same viewport.
- [ ] `AliasFreshnessNote` is present and legible in the `subject="other"` story and absent in
      `subject="self"`, confirmed by overlaying the two identity-bar screenshots.
- [ ] The never-ranked-third-party story renders the identical info-callout copy as the
      never-ranked-own-profile story from §10, differing only in `subject`'s other effects.
- [ ] The not-found story shows a single danger callout and a link back to search — no field on the
      page distinguishes "does not exist" from any other reason a profile could 404.
- [ ] `subject="self"` and `subject="other"` stories are visually identical in `RatingBoard`, down to
      spacing and figure alignment, when given the same rating data — the only permitted differences
      are the four named in §11.1.
