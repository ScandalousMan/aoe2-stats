# FavouritesList

**Component**: `src/components/FavouritesList/` (internal anatomy piece: `FavouriteRow` — not a
separate export, the same relationship `ParticipantRow` has to `MatchDetailPanel` in
[`match-history.md`](./match-history.md) and `ReplayAvailabilityRow` has to `ReplayAvailabilityList`)
**Feature**: 003, US5 — consumed by `apps/web/src/routes/favourites.tsx` (003 T349)
**Requirements**: FR-012, FR-013, FR-014, FR-015, FR-016, FR-017. US5 scenarios 2, 3, 5.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `StatValue` (each entry's current
standing), `Callout`, `Skeleton`, `Button`. [`favourite-toggle.md`](./favourite-toggle.md) — the
per-entry remove control **is** `FavouriteToggle`, not a second one-off button.
[`profile-summary.md`](./profile-summary.md) — `CountryLabel`'s convention (country as text, optional
`aria-hidden` glyph) and the `StatValue` empty/stale treatment for a standing, both reused rather than
reinvented. [`player-search.md`](./player-search.md) — the "absent, not blank-filled" discipline for a
field a row cannot supply.

## 1. Purpose

Let a signed-in user find the players they care about again from one place, without searching — each
entry showing that player's current standing and reaching their profile in a single step (FR-014) —
and let them remove one from here too (FR-013, US5 scenario 2).

## 2. Anatomy

```
FavouritesList                                        one per /favourites route, one row per favourite
├─ Heading              h1 "Favourites" — present in every state, including empty and signed-out
└─ FavouriteRow ×n      newest-favourited first (the natural order of the favourites table's created_at)
   ├─ ProfileLink       the alias (+ optional clan tag), a link to the player's profile — FR-014's
   │                    "one step". The link wraps alias, country and standing so the whole informative
   │                    block is one target; the remove control is a SEPARATE focus stop beside it (§4)
   │  ├─ Alias          text-primary, semibold
   │  ├─ Clan           optional "[TAG]", text-secondary, beside the alias
   │  ├─ CountryLabel   country in text, optional aria-hidden glyph — never absent when country is known
   │  └─ Standing       StatValue/compact — current rating and rank on the player's primary ladder (§4)
   └─ RemoveControl     FavouriteToggle in its marked state ("Remove from favourites"), trailing —
                        the same component, not a bespoke button (favourite-toggle.md)
```

`FavouriteRow` is deliberately **not** a whole-row link the way `PlayerResultRow` and `MatchRow` are:
it carries a second thing to do (remove), so — like `ReplayAvailabilityRow`, which pairs a label with a
`DownloadAction` — the informative block is one link and the action is a second, distinct focus stop.
Two focus stops per row, not one; never a `<div>` with a click handler wrapping a nested button.

**IP note**: no player avatar, no clan crest, no country flag illustration beyond a free-licensed,
`aria-hidden` glyph beside the country **name in text** — the same rule and licensing obligation
`profile-summary.md` §2 and `player-search.md` §2 state for `CountryLabel`. Constitution X.

## 3. Variants and sizes

No variant axis. `FavouritesList` takes its entire content from the favourites the API returns; each
`FavouriteRow` varies only with the data it is given (§4). Sizing is responsive, not an independent
axis (§8).

## 4. What an entry shows, and the gaps it must admit rather than paper over (FR-014, FR-015)

Each entry is fed the player and their **current standing** exactly as `GET /api/favourites` returns it
(`contracts/http-api.md`: "Each entry with the player and current standing"). "Current standing" is the
player's rating and rank on their primary ladder — the same figures `profile-summary.md`'s
`RatingBoard` shows, in a single `StatValue/compact` per row so the whole list reads as a comparable
column, not the full board. FR-014 asks for standing "per entry" and this is the smallest honest
answer; the full board is one click away on the profile the row links to.

**Standing is `StatValue`, so it inherits `StatValue`'s three honesty rules unchanged** — this is why
it is not hand-rolled text:

- **Never a placeholder numeral.** A player whose standing has not loaded shows `StatValue`'s loading
  state (a `number` skeleton), never `0`, `–` or `--` (`StatValue` §loading — "the worst failure this
  design system can produce").
- **Never played a ranked ladder** (US5 scenario 3 reaches players of any kind; spec.md edge case: "a
  favourited player who never played ranked"): `StatValue`'s **empty** state — the value slot states
  "Not ranked yet" in words, `type-supporting`/`text-secondary` (T532), reusing the row's own
  `secondaryLine` rather than repeating it beneath the value — exactly as `profile-summary.md` §5
  empty case 2 renders a provisional profile. Never a punctuation mark a reader has to interpret; the
  words are `text-secondary` so they can never be misread as a measured `text-primary` figure.
- **Standing could not be refreshed** (spec.md edge case: "a favourited player who later disappears
  from the source"): `StatValue`'s **error** state — the last-known figure at full contrast with a
  secondary line stating when it was measured and that the refresh failed, per `StatValue` §error
  ("stale and labelled beats blank; blank beats wrong"). The row still links to the profile; a
  disappeared player is not silently dropped from the list, which would lose the user's own bookmark
  with no explanation.

**`clan` and `country` are absent when unknown, never blank-filled** — no empty bracket, no em dash
standing in for a missing country, the same rule `player-search.md` §4 states. Two favourites sharing a
name and country are still each one click from their distinct profiles.

**Nothing here counts or discloses favouriters (FR-015).** The list shows only the caller's own
favourites; there is no per-entry "N people follow this player", no aggregate, and
`FavouriteRowProps` carries no field one could be built from — the same absence-by-construction
`data-model.md` states for the `favourites` table ("a fact this system must not be able to answer").
And a row here triggers no capture of the favourited player's recordings (FR-012): the only actions a
row offers are the profile link and the `FavouriteToggle` remove.

## 5. States

The state vocabulary is closed (README); all eight are answered. The whole-list states below are
distinct from each `FavouriteRow`'s own per-field states (§4) and from `RemoveControl`'s own states,
which are `FavouriteToggle`'s (`favourite-toggle.md` §5).

**default** — `Heading` above the list of `FavouriteRow`s, newest favourited first, each with its
standing and a trailing remove control.

**hover / focus-visible / active** — `ProfileLink`: whole-block hover fill `surface-sunken`, focus ring
on the link wrapper inset so it never crops the standing's digits (`player-search.md` and
`profile-summary.md`'s identical rule for figures). `RemoveControl`: `FavouriteToggle`'s own
hover/focus/active. The two never share a hover: the informative block lighting up and the remove
button lighting up are different affordances and read as such.

**disabled** — the list has no disabled form. `RemoveControl` is disabled only transiently while its
own `DELETE` is in flight (`FavouriteToggle` §loading); removing is never blocked by the favourites
bound (`favourite-toggle.md` §5 — the bound gates only adding).

**loading** — before `GET /api/favourites` answers: `Heading` renders, then `Skeleton/block` rows at
`FavouriteRow`'s own footprint (as many as the last known count, else 3), per `Skeleton`'s 200 ms /
10 s rule. No `0`, no `–`, no partial row (`match-history.md` and `player-search.md`'s identical rule).

**error** — `GET /api/favourites` failed (network, or this service's API unavailable), distinct from
the signed-out `401` below: `Callout/danger` in place of the list — _"We could not load your
favourites. Try again."_ — with a retry. `Heading` stays above it. A **row-level** failure (one
player's standing could not refresh) is not this state; it is `StatValue`'s per-entry error (§4), so a
single unreachable player never blanks the whole list.

**empty** — the caller is signed in and has **no** favourites yet (the state that must exist, not be
skipped): `Callout/info` beneath the `Heading` — _"You have not added any favourites yet. Open any
player's profile and choose “Add to favourites”."_ `info`, not `danger`: nothing went wrong, and the
copy points at the exact route to fill the list (`shared-primitives.md`'s `info` rule — "nothing went
wrong… anything the user's own history caused"). The `Heading` renders above it: the page is real even
when its list is not, the same discipline `match-history.md` §5 and `profile-summary.md` §5 apply to
their own empty states.

### 5a. signed-out — `401 sign_in_required` (US5 scenario 5, FR-015)

Reaching `/favourites` without a session cannot show favourites — they are private (FR-015) and there
are none to show. The whole list is replaced by a sign-in prompt that **preserves the user's place**:
`Callout/info` beneath the `Heading` — _"Sign in to see the players you've favourited."_ — with a
`Button/primary` "Sign in" that routes to [`sign-in-screen.md`](./sign-in-screen.md) **carrying
`/favourites` as the return location**, so after signing in the user lands back on this page, where they
were (US5 scenario 5). This mirrors `favourite-toggle.md` §5a's signed-out behaviour on the profile —
both lean on the `401 sign_in_required` code (`contracts/http-api.md`) whose entire purpose is to let
the client return the user to where they were. No favourited state and no player is shown before a
session exists.

Under the closed-beta allowlist this route is currently reached only by signed-in users
(spec.md Assumptions), so this state is not yet reachable in production; it is specified in full because
US5 scenario 5 is written against it and it must exist the moment the allowlist is lifted.

## 6. Tokens used

Colour, all via `StatValue`, `Callout`, `Skeleton`, `Button` and `FavouriteToggle` — no new token and
no new pair (each is already in `specs/README.md`'s measured table and asserted in
`tokens/build-tokens.test.mjs`): `background` (page), `surface` (row), `surface-raised` (`Callout` fill,
via that component), `surface-sunken` (`ProfileLink` hover, `Skeleton` fill), `border` (row
separators), `border-strong` (`Button`/interactive boundaries), `text-primary` (alias, standing
figure), `text-secondary` (clan, country, labels, standing's "Not ranked yet"/freshness secondary
line), `success` / `danger` (a rating delta's sign, via `StatValue`), `info` / `danger` (the two whole-
list `Callout` tones in §5/§5a), `accent` family (the "Sign in" `Button/primary`, via `Button`),
`focus-ring`.

Typography: `mono` for `Standing`'s figures (DS-8 — the same reasoning every stacked-figure list in
this system gives), `sans` for everything else. Sizes: `Heading` `2xl`; alias `sm` `semibold`; clan,
country, standing label `xs`; standing value `lg` (`StatValue/compact`). Weights `semibold` on alias
and figures, `normal` elsewhere. Tracking `tight` on the standing value (`StatValue`'s own).

Radius `lg` (row card at 375, `Callout` via that component), `md` (buttons). Elevation `none`
throughout — `profile-summary.md`'s reasoning against shadowed cards in a fast-read list applies here
identically. Motion `duration.fast` + `easing.standard` on `ProfileLink` hover; **no motion on the
standing figure** — no count-up, no entrance fade (`StatValue`'s own rule, README rule 1). Under
`prefers-reduced-motion`, `duration.instant`.

Gaps in play: **DS-4** (focus ring). **DS-8 closed** (T531) — `Standing`'s tabular alignment now
comes from `type-numeric`'s `tabular-nums`.

## 7. Spacing

| Between                                             | Step      |
| --------------------------------------------------- | --------- |
| `Heading` to list (or to empty/error/sign-in state) | `space-6` |
| Between `FavouriteRow` cards (375)                  | `space-3` |
| `FavouriteRow` padding (375 card)                   | `space-4` |
| `FavouriteRow` row padding-block (from 768)         | `space-3` |
| Alias to clan                                       | `space-2` |
| Alias line to country/standing                      | `space-1` |
| `ProfileLink` block to `RemoveControl`              | `space-4` |

## 8. Responsive

- **375** — each `FavouriteRow` is a stacked full-width card: alias + clan on the first line, country
  and standing wrapping onto a second line, `RemoveControl` at `Button`'s touch size (`lg`, 48px) full
  width beneath. No field truncates or ellipsises (`profile-summary.md`'s figure rule extended to every
  field — a half-visible alias defeats the point of a bookmark list).
- **768** — alias/country/standing sit on one row; `RemoveControl` becomes intrinsic-width,
  right-aligned in the row. Still one `ProfileLink` and one `RemoveControl` per row.
- **1280** — unchanged from 768 beyond the column's own width. A full `<table>` transform (as
  `profile-summary.md` and `match-history.md` adopt) is **not** used: this is a short, non-sortable
  list of bookmarks with one comparable figure per row, read as fast as a table at this width, and a
  second DOM shape would be one more place to drift — the same reasoning `player-search.md` §8 and
  `replay-availability.md` §9 give for keeping one shape.

`Skeleton` row count and footprint match the loaded footprint at the same viewport, so
loading-to-loaded shows no reflow (`match-history.md`'s and `player-search.md`'s identical criterion).

**Do not render both layouts and hide one** — one DOM, restructured at the breakpoint.

## 9. Accessibility

- `FavouritesList` is a `<section aria-labelledby>` (or `<main>`) headed by `Heading` (`<h1>`, the page
  title); the rows are a `<ul>`/`<li>` at every viewport (§8 keeps one DOM shape, unlike the table
  transforms elsewhere).
- Each `FavouriteRow` has exactly two focus stops in document order: `ProfileLink` (a real `<a>`
  wrapping alias, country and standing) then `RemoveControl` (`FavouriteToggle`'s `<button>`). Never a
  nested interactive-in-interactive; never a `<div>` with a click handler.
- `Standing` uses `StatValue`'s own semantics — label and value associated (`<dt>`/`<dd>`), a delta's
  sign is a character in the accessible name ("+12"/"−8"), never a rotated glyph. Figures are selectable
  text, never an image or canvas (`profile-summary.md`'s rule — a standing a user cannot copy is one
  they retype by hand).
- `RemoveControl` carries `FavouriteToggle`'s accessibility whole (`favourite-toggle.md` §9):
  `aria-pressed="true"` in its marked state, label "Remove from favourites", ≥ 44px touch target. This
  component re-implements none of it.
- The whole-list `Callout`s (empty/info, error/danger, sign-in/info) follow `Callout`'s tone-to-role
  mapping — `role="status"` for `info`, `role="alert"` for `danger`.
- The signed-out "Sign in" action is a real activation that navigates carrying the return location, so a
  keyboard or screen-reader user reaches the sign-in screen and returns to `/favourites` the same way a
  pointer user does (§5a).
- **Loading (T532, FR-054)**: the `<ul>` of `Skeleton` rows carries `aria-busy="true"` itself — one
  announcement for the whole list, never once per row's `Skeleton` (each stays `aria-hidden`, its own
  contract). See `shared-primitives.md`'s `StatValue` section for the general rule this follows.
- Contrast per `specs/README.md`'s measured table, entirely through the primitives above.
- Usable at 200% zoom and 320px logical width without horizontal scrolling; no field ellipsises at any
  viewport (§8).

## 10. Visual acceptance criteria

- [ ] Each row shows the player's alias as a link **and** a separate "Remove from favourites" control —
      counting focusable elements in a row story finds exactly two, in the order link-then-remove, never
      a nested button inside the link.
- [ ] A row seeded with a real standing shows the rating and rank in `type-numeric`, aligning
      digit-for-digit down the column against other rows in the same frame.
- [ ] A row seeded with a never-ranked player shows "Not ranked yet" in words, `text-secondary`, in the
      standing position — never `0`, never an em dash, never a `text-primary` numeral — placed beside a
      rated row to confirm the two are distinguishable.
- [ ] A row seeded with an unrefreshable standing shows the last-known figure at full contrast with a
      "measured … / could not refresh" secondary line, and the row still links to the profile — the
      disappeared player is not dropped from the list.
- [ ] The empty story (signed in, no favourites) shows the `Heading` above an **info** callout naming
      the exact way to add a favourite — never a blank page and never a danger tone.
- [ ] The load-failed story shows a **danger** callout with a retry, visibly different in tone and copy
      from the empty story, so "nothing added" and "could not load" are never confused (a single side-
      by-side comparison proves it).
- [ ] The signed-out story shows the `Heading`, an **info** callout, and a "Sign in" primary button, and
      no favourited player anywhere in the frame (FR-015); activating "Sign in" in the story routes to
      the sign-in screen carrying `/favourites` as the return location.
- [ ] The loading story's skeleton row count matches the loaded story's row count at the same viewport,
      with no reflow between the two.
- [ ] Converting any state's screenshot to greyscale leaves the callout tones (`info` vs `danger`)
      distinguishable by heading and body copy alone, and every standing figure still legible.
- [ ] No avatar, clan crest or flag illustration in any frame — only text and, at most, a free-licensed
      `aria-hidden` country glyph.
