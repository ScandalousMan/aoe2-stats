# ProfileSummary

**Component**: `src/components/ProfileSummary/`
**Feature**: 001, US1 — consumed by `apps/web/src/routes/dashboard.tsx` and
`apps/web/src/features/profile/` (T037). **Extended by 003, US1** (§11) — consumed by
`apps/web/src/routes/players.$profileId.tsx` (003 T322), where it presents a profile that is not the
signed-in user's own. **Extended by 004, US2** (§12) — the alias as the heading, the numeric id
demoted, the country flag and the Steam avatar.
**Requirements**: FR-008 (rating, rank, win/loss per leaderboard), FR-043 (one primary, others
reachable), FR-045 (never reveal that two linked accounts are one person), FR-004 (unlink trigger),
FR-007. SC-004. **§11 also carries 003's FR-006, FR-008, FR-008a, FR-009, FR-010, FR-013, FR-014**,
and **§12 carries 004's FR-007, FR-008, FR-008a and FR-013, and SC-002** — each prefixed `003` or
`004` throughout this file to keep them apart from 001's own FR-008/FR-004/FR-007/FR-045 above, and
from each other: all three features number a requirement `FR-008`, and 003 and 004 both have an
`FR-008a` about different things.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `StatValue`, `Menu`, `Badge`,
`Button`, `Callout`, `Skeleton`. §11 also depends on
[`player-search.md`](./player-search.md)'s `PlayerSearchResult` shape for `alias_observed_at`. §12
depends on [`country-flag.md`](./country-flag.md), [`player-avatar.md`](./player-avatar.md) and
[`game-asset-tokens.md`](./game-asset-tokens.md)'s `icon` size family (DS-7, closed).

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

---

## 12. A profile says who the player is (004, US2 — extends §§1–11, does not replace them)

**What changed underneath this component, and none of it is a redesign.** The pack this file's §2 IP
note anticipated now exists and is licence-recorded — `packages/game-assets/flags/LICENCE.md`, the
MIT `lipis/flag-icons` 4x3 set — so the flag "if used at all" is now specified rather than
hypothetical. `aoe_profiles.avatar_hash` exists and is served (004 T421, T426;
`contracts/http-api.md`), so the avatar has a fact to render. And the identity bar has, since 001,
been printing `country` **as the API serves it**, which is a lowercase two-letter code: the same
identifier-instead-of-a-person defect this feature exists to remove, in miniature, one line under the
alias.

Everything in §§1–11 applies unchanged. This section states only what the identity of a **person**
introduces, and — where it changes an earlier rule — says so in §12.1 rather than quietly.

**004's own requirement numbers collide with 001's and 003's** (all three have an `FR-008`; 003 and
004 both have an `FR-008a`), so every reference below is prefixed `004`.

### 12.1 What §12 supersedes, and what it leaves standing

| Earlier text                                                                     | Status                                                                                                                                                                                                                                          |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §2's `IdentityBar` anatomy                                                       | **Widened** by §12.6: `PlayerAvatar` leads it, and `CountryLabel` becomes [`country-flag.md`](./country-flag.md)'s flag-plus-name pair. Nothing is removed.                                                                                     |
| §2's `CountryLabel` line, "country name in text"                                 | **Unchanged as written, corrected in practice.** It always said _name_; the component shipped the raw code. §12.4 fixes what renders, not what this file asked for.                                                                             |
| §2's IP note on flags                                                            | **Satisfied, not superseded.** "A free-licensed set whose licence is recorded here before first use" is now `packages/game-assets/flags/` (MIT), and the flag is still decorative beside the country in text. The rest of the note stands.      |
| §2's `ProfileSwitcher` trigger showing the alias                                 | **Widened** by §12.3: when there is no alias, the trigger and the `<h2>` show the fallback heading. It is still text plus a chevron, never an icon.                                                                                             |
| §4's FR-045 rules                                                                | **Unchanged, and extended by §12.5**: "no shared avatar, no visual pairing" now has a picture to forbid, so no avatar appears in a switcher item.                                                                                               |
| §5's empty case 1, "No leaderboard has a rating for this profile yet"            | **Unchanged, and load-bearing.** It is a real and correct outcome that profile `1807091` genuinely has (spec.md's own edge case). Every temptation in this work is to make it look like something went wrong; §12.7 states what may not change. |
| §7's "Switcher trigger to country label `space-3`", §8's identity-bar stacking   | **Unchanged.** §12.8 adds two rows and changes none.                                                                                                                                                                                            |
| §9's `<h2>` section heading, §11.1's four `subject="other"` differences, §5, §10 | **Unchanged, and load-bearing.** §12 adds an avatar, a flag and a fallback to them; it removes none of them, and the avatar and flag are **not** a fifth `subject` difference (§12.5).                                                          |

### 12.2 The fallback ladder: three rules that look like one

004 FR-007, FR-008 and FR-008a read as one sentence about missing data. They are three rules with
three different answers, and collapsing them is how a profile ends up with a blank heading, a gap
where a flag was, or a broken image — each a different defect with a different cause.

| What is missing               | The rule                                                              | The failure it exists to prevent                                                                   |
| ----------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **alias** (004 FR-007)        | The numeric id **becomes the heading**, never a blank one (§12.3)     | An empty `<h2>`, and a `<section aria-labelledby>` pointing at nothing                             |
| **country** (004 FR-008)      | The flag **and its label are omitted cleanly** (§12.4)                | A reserved gap, an em dash or a globe glyph that reads as "something failed here"                  |
| **avatar hash** (004 FR-008a) | The **same neutral placeholder** as a hash that fails to load (§12.5) | A broken-image glyph, and a viewer who can tell a stale hash from a missing one and act on neither |

Read the differences, not the similarity: one **substitutes**, one **removes**, one **stands in**.
Substituting for a missing country ("Unknown") or removing the avatar's space would each be the wrong
rule applied to the wrong field.

**All three fire at once on a real production profile** — one discovered from a match, never searched,
never seen by the companion provider. That is a story T437 ships (§12.7), not a hypothetical.

### 12.3 Rule 1 — no alias: the id becomes the heading, never a blank one (004 FR-007)

**When it fires.** `alias` is absent, `null`, or **blank after trimming**. The blank case is the one
that actually happens: the API types `alias` as a non-null `string`
(`apps/web/src/features/players/api.ts` asserts `typeof body.alias === "string"`), so a profile with
no persona name arrives as `""`, and a component that checks only for `undefined` renders an empty
heading — precisely what 004 FR-007 forbids. The test is emptiness, not nullishness.

**What renders.** The `<h2>` reads **"Player 1807091"** — the id, prefixed by what it is an id _of_.

- **Not the bare number.** This whole feature exists because `1807091` stood in for a person; an
  unlabelled numeral as the page's heading repeats that. The prefix follows the rule
  [`match-history.md`](./match-history.md) §11.2 already fixed for an unnamed identifier: "a label
  prefix that says what it is an id of, never the bare number".
- **`font-mono`**, at the alias's own size (`xl`) and weight (`semibold`) — an id is data, a name is
  prose, and DS-8 keeps the two out of one typeface.
- **`text-primary`, and here §12 deliberately diverges from §11.2's `text-secondary`.** An unnamed
  civilisation is a fact this service admits it could not resolve. This is not that: the profile
  really is identified by this number, exactly and verifiably. The page's subject may not be typeset
  one step down the hierarchy, or the page has no visible subject at all.
- **Never** "Unknown player", "Anonymous", an em dash, a placeholder name, or an `<h2>` with a
  `Skeleton` left in it after loading finished.

**Three consequences an implementer would otherwise decide separately:**

1. **`ProfileId` is omitted while this rule is in force.** The same number twice — once at `xl`, once
   at `xs` beneath it — reads as a rendering fault, and there is nothing to demote it beneath. §2's
   "the identifier support will ask for" is still on screen; it is the heading.
2. **`AliasFreshnessNote` is absent** (§11.1.4). "Last seen as ⟨nothing⟩ on 12 Aug 2026" is a
   sentence with a hole in it, and §5's "absent, not blank-filled" discipline decides it.
3. **The switcher trigger shows the same fallback string**, and its accessible name becomes
   "Player 1807091, switch profile" — §9's rule that the trigger's name contains the word "profile"
   is unchanged, and is what keeps it from being announced as a bare numeral.

### 12.4 Rule 2 — no country: the flag is omitted cleanly (004 FR-008)

`CountryLabel` is [`CountryFlag`](./country-flag.md): the flag, then the country **name in words**.
The behaviour is specified in that file; this section fixes only what the caller owes.

- **The code never reaches the screen.** `apps/web` resolves `country` (ISO 3166-1 alpha-2) to an
  English display name and to a pack URL before either reaches this component
  (`country-flag.md` §2a, T438). `ViewedProfile` therefore carries `countryName` and `countryFlagUrl`
  and **replaces** today's raw `country` field — carrying both the code and the name would leave two
  fields that can disagree about the same fact.
- **The pair sits outside the switcher trigger, immediately after it**, at §7's existing `space-3`.
  Inside the trigger, the country would join the control's accessible name — "Hera France, switch
  profile" — making a fact about a person part of a button's label. The flag is never inside a
  control.
- **No country at all: nothing renders**, and the line closes up. No reserved width, no em dash, no
  "Unknown country", no globe. A profile without a country must look like a profile that never had
  one, not one that lost it — which is the entire content of 004 FR-008's "omit it cleanly".
- **A country whose flag the pack does not cover**: the name alone, no frame
  (`country-flag.md` §4). The reader is told where the player is from; they were never owed a picture
  of it.

### 12.5 Rule 3 — no avatar, or one that fails: the same neutral placeholder (004 FR-008a)

[`PlayerAvatar`](./player-avatar.md) leads `IdentityBar`, at `md` (`icon-2xl`, 64px) in `board` and
`sm` (`icon-lg`, 32px) in `compact`. It takes `avatarHash` — a hash, never a URL — and builds the
Steam CDN URL itself, which is that file's §2b and the one place in this system a URL is constructed.

What this file owes on top of it:

- **A missing hash and a hash that fails to load render identically, to the pixel**
  (`player-avatar.md` §4). A viewer cannot act on either, so a difference between them would be an
  invitation to try. This is the same identical-render discipline
  [`civilisation-icon.md`](./civilisation-icon.md) §4 applies to an emblem that fails to load.
- **Exactly one avatar per rendered `ProfileSummary`**, in `IdentityBar`. **Never in a switcher menu
  item** — §4's FR-045 list forbids "shared avatar… visual pairing", and a column of identical
  avatars beside a user's linked aliases is exactly that picture. The switcher stays a list of names.
- **It is not a fifth `subject` difference.** §11.1 names four differences between `self` and `other`
  and this is not among them: both subjects show the viewed profile's own avatar, at the same size,
  in the same position, from the same prop. A third party's avatar is public data from a public
  source, recorded in the processing register (004 T427).
- **The hash is an unverified third-party claim** (constitution IX): shown as reported, never used to
  infer that two profiles are one person, and never the basis of any affordance.

### 12.6 The widened `IdentityBar`

```
IdentityBar (widened — §2's parts, rearranged around two new ones)
├─ PlayerAvatar        md (64px) in `board`, sm (32px) in `compact`. Leads, at EVERY viewport
└─ IdentityColumn
   ├─ NameLine
   │  ├─ ProfileSwitcher | AliasHeading    the <h2>: the alias, or §12.3's "Player <id>"
   │  └─ CountryFlag                       flag + country name — outside the trigger, after it
   ├─ ProfileId                            font-mono xs text-secondary — ABSENT under §12.3
   ├─ AliasFreshnessNote                   subject="other" only; absent when there is no alias
   └─ (ProfileActions | FavouriteToggle)   §2 / §11.1.3, unchanged, still right-aligned from md
```

**The order is the reading order and the importance order**: face, name, country, identifier. A
screen reader and a sighted reader get the same four facts in the same sequence, and the one a
support ticket needs is last because it is the one a person reads least.

**What this bar must not become**, each because a peer site does it and it costs the numbers below:

- **A centred hero card** — a large avatar above a centred name above the ratings. It reads as a
  social profile and pushes the rating board a screen further down; README rule 1 settles that trade.
- **A banner or cover image behind the identity bar.** No texture, no artwork, no parchment
  photograph — and nothing at all behind a figure (README rule 1 again).
- **A clan crest.** No pack covers one, `player-search.md` §2 forbids it, and a clan tag is text.
- **An avatar that is a link, or a flag that filters by country.** Neither exists in 004; adding one
  is a spec change, and it would need the 44px hit area `game-asset-tokens.md` fixes `icon-xl` for.

### 12.7 States §5 and §11.2 did not need to name

**default / hover / focus-visible / active / disabled** — unchanged. Neither new part is
interactive, neither takes a `tabindex`, and neither has a hover: the identity bar's focus stops are
still exactly the switcher trigger and the actions beside it.

**loading** — §5's rule is unchanged and gains one part: the identity-bar skeleton now includes a
`Skeleton/block` at the avatar's exact footprint (same square, same size token, same `radius-md`)
beside the existing alias `Skeleton/text`, so nothing reflows when the profile resolves.
**No skeleton is drawn for the flag**: whether a country exists is not known until the data arrives,
so reserving space for it would leave a gap on every profile that has none (`country-flag.md` §4).

**error** — two new failure modes, and both render as an _absence_, never as an error: a flag image
that fails leaves the country name alone; an avatar that fails leaves the neutral placeholder.
Neither produces a callout, a tone change or a retry — the profile is fully readable without either
picture, and telling a user that an image did not load asks them to act on something they cannot.
§5's two error cases are about **ratings** and are unchanged.

**empty** — §5's three cases and §11.2's fourth are unchanged. Two things to hold:

> **"No ratings yet" does not move.** Same `Callout/info`, same copy, same tone, same position
> relative to the identity bar. It does not become a warning, does not gain a retry, does not gain an
> illustration, and is not hidden behind a fold. It is the correct rendering of a real fact about
> profile `1807091`, and the identity bar above it — now a face, a name and a country — is what makes
> the page read as intentional rather than broken. Making the calm state look like a failure is the
> one way this section can damage what §5 got right.

§12 adds one empty state neither §5 nor §11.2 had to name, because it is the shape of a profile this
service discovered from a match and never enriched:

> **A profile with no alias, no country and no avatar hash renders in full.** Heading:
> "Player 1807091" (§12.3). Avatar: the neutral placeholder (§12.5). Country: absent entirely
> (§12.4). `ProfileId`: omitted, because the heading is already the id. The rating board renders
> whatever it has, including "No ratings yet". **Nothing is blank, nothing is an error, and nothing
> apologises.** This is a legitimate resting state, not a broken one.

### 12.8 Tokens, spacing, responsive, accessibility — the delta only

**Tokens.** No new token and no new gap. Via the two components: `border` (the flag's frame,
decorative), `border-strong` (the avatar's frame, meaning-bearing, 3:1), `surface-sunken` (the
avatar's placeholder fill), `icon-sm` / `icon-md` / `icon-lg` / `icon-2xl`, `radius-sm`, `radius-md`.
§6's own list is otherwise unchanged. `mono` now also carries §12.3's fallback heading, which is why
**DS-8** is in play for this section and not only for the rating board.

**Contrast pairing.** This component's root is `bg-background`
(`src/components/ProfileSummary/index.tsx`), so its pairs are README's `background` rows, per that
file's own pairing convention (T034c: name the background the component actually paints).
`border-strong` on `background` is measured and asserted in **both** themes, which is what the
avatar's frame rides on. `text-secondary` on `background` — the country name and `ProfileId` — is
measured in the light theme, the tight one; the dark table carries no `background` row for it, and
dark `background` is darker than dark `surface`, so the pair is no tighter there than the `surface`
row already measured. A row should be added the next time README's table is recomputed; nothing in
§12 is blocked on it, because no token here is new.

**Spacing** (added to §7; nothing there changes):

| Between                                   | Step      |
| ----------------------------------------- | --------- |
| Avatar to the identity column             | `space-4` |
| Flag to the country name beside it        | `space-2` |
| Heading (or switcher trigger) to the flag | `space-3` |

The third row is §7's existing "switcher trigger to country label" under its widened name, restated
so the table is readable without cross-referencing, not changed.

**Responsive.** §8's structure, breakpoints and one-DOM rule are unchanged.

- **375** — the avatar stays **beside** the identity column, never stacked above it: a 64px block on
  its own line pushes the ratings further below the fold, and the ratings are what the user came for.
  The country pair may wrap **as a unit** onto the line below the heading; it never wraps between the
  flag and its name.
- **768 / 1280** — as §8, with the avatar at the same size. The identity bar's height is set by the
  avatar at `board`, which is why nothing else in it grew.
- **320px / 200% zoom** — both marks are rem-sized and grow with the text. §9's "figures never
  ellipsise" extends to §12.3's fallback heading: a truncated identifier is a **wrong** identifier,
  so it wraps rather than clipping.

**Accessibility.** §9 is unchanged; the delta is small because both marks were specified to add
nothing to it.

- The `<h2>` §9's `aria-labelledby` points at now **always resolves to text** — an alias, or
  "Player 1807091". Before §12.3 a blank alias left the section labelled by an empty element.
- Both images are decorative: the flag is `alt=""` beside the country in text (this file's §2 IP note
  already required exactly that), and the avatar is `alt=""` beside the heading. No fact is announced
  twice, and the avatar's placeholder is `aria-hidden` — its absence has no meaning a screen-reader
  user could act on.
- The flag never enters the switcher trigger's accessible name (§12.4).
- No new tab stop and no new touch target: nothing added here is interactive, so §9's ≥44px rule
  applies only if a later feature makes the avatar a link.
- The avatar's `<img>` carries `referrerpolicy="no-referrer"` (`player-avatar.md` §8): the Steam CDN
  necessarily learns the viewer's IP, but it must not also learn which profile they were reading.

### 12.9 Visual acceptance criteria (additional to §10 and §11.4)

**The ladder — one story per rule, and they are what SC-002 reduces to**

- [ ] The full-profile story shows, in one frame at 375, 768 and 1280: the avatar leading, the alias
      as the largest text in the identity bar, a flag with a country **name** beside it, and the
      numeric id demoted beneath — smaller and in `text-secondary`.
- [ ] The alias-less story's heading reads **"Player <id>"** in the monospaced family at the alias's
      own size, and the id appears **exactly once** in the frame — no demoted duplicate beneath it.
- [ ] The alias-less story shows no blank heading, no "Unknown", no em dash and no leftover skeleton,
      and no `AliasFreshnessNote` — in both themes.
- [ ] The country-less story shows **no flag and no country label at all**: no gap, no em dash, no
      globe. Overlaid on the full-profile story, the heading sits at the identical position.
- [ ] **No two-letter country code appears anywhere in any story**, which is the identity-bar half of
      SC-002.
- [ ] The absent-avatar story and the failed-avatar story are **pixel-identical**, in both themes.
- [ ] The three-absence story (no alias, no country, no avatar) shows a heading, a framed placeholder
      and the rating board: nothing blank, no `danger` or `warning` tone anywhere in the frame.

**The state that must not change**

- [ ] The "No ratings yet" story still shows an **info** callout with §5's copy verbatim, no retry
      button and no illustration; the identity bar above it renders in full.
- [ ] Placed beside the pre-004 baseline, the only differences in that story are the identity bar's
      new avatar and flag — the callout's copy, tone and internal spacing are untouched.

**Composition, privacy and craft**

- [ ] The open-switcher story shows **no avatar and no flag inside any menu item** (FR-045), in both
      themes.
- [ ] `subject="self"` and `subject="other"` stories with the same profile data show an identical
      avatar, flag and heading treatment; the only differences are the four §11.1 names.
- [ ] At 375 the avatar sits beside the heading, not above it, and the identity bar is not centred.
- [ ] No banner, cover image, texture or artwork sits behind the identity bar or across any figure.
- [ ] Focus ring visible and unclipped on the switcher trigger with the avatar beside it; **neither
      the avatar nor the flag ever shows a focus ring** (tab through the story to confirm neither is
      a stop).
- [ ] Zero broken or missing images across every story in both themes, and the browser network panel
      shows no request under `/game-assets/flags/` returning 404 (SC-005). A 404 there is a defect in
      the resolver contract, not a missing file.
- [ ] Converting any story to greyscale leaves the heading, the country name and the id fully
      readable; only the flag and the avatar lose information, which is the point — nothing was
      riding on either.
