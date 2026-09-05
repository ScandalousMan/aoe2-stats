# MapThumbnail

**Component**: `src/components/MapThumbnail/` (T429)
**Feature**: 004, US1 — consumed by `MatchRow` and `MatchDetailPanel`
([`match-history.md`](./match-history.md) §12).
**Requirements**: FR-002, FR-010, FR-013, FR-016. SC-001, SC-005.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — the `icon` size family (DS-7,
closed). [`shared-primitives.md`](./shared-primitives.md) — `Skeleton`, for the caller's loading
footprint. [`match-history.md`](./match-history.md) §11.2 — `UnresolvedIdentifier`, for the
no-map-at-all case.
**Asset origin** (README rule 3): a file in `packages/game-assets/maps/`, licence-recorded per
`specs/004-visual-parity/contracts/asset-pack.md`. The component never imports it and never reaches
into the pack; the caller resolves `mapThumbnail(mapName)` and passes the result — `undefined`
included — straight through.

## 1. Purpose

Show which map a match was played on, as the minimap a player recognises instantly, beside the map's
name — so a history list is scannable by shape as well as readable by word.

## 2. Anatomy

```
MapThumbnail                     one group; the thumbnail and the name are a single unit
├─ Frame       a square box with a 1px `border` hairline and `radius-md`, drawn ONLY when an
│              image is actually rendered inside it (§4 empty)
│  └─ Image    <img>, `object-fit: contain`, never stretched or cropped
└─ Name        the map name, verbatim from `matches.map_name`, always rendered, selectable text
```

The three rules stated in [`match-history.md`](./match-history.md) §12.1 govern this component too.
Two of them decide something here:

- **The absent-asset state is the prop being `undefined`, rendering the readable label alone.** The
  map identifier space is unbounded — custom and tournament maps exist that no pack can ever cover
  (data-model.md §4: "This is the designed path, not a defect") — so a missing thumbnail is a
  routine, expected render, not a degraded one. **The frame does not survive the image**: an empty
  bordered box is a placeholder image drawn in CSS, and it says "something should be here" and
  nothing else.
- **Imagery is never the only carrier.** There is no thumbnail-only mode. The name always renders,
  because a minimap without a name is a puzzle and two Arabia-shaped maps are not the same map.

## 3. Variants and sizes

No tone or style variants. Three sizes, all from the existing `icon` family — no new token:

| Size             | Token             | Where                                                         |
| ---------------- | ----------------- | ------------------------------------------------------------- |
| `sm`             | `icon-lg` (32px)  | `MatchRow`'s 1280 table row — see §7 for why this size exists |
| `md` _(default)_ | `icon-2xl` (64px) | `MatchRow`'s 375/768 card layout, and any dense list          |
| `lg`             | `icon-3xl` (96px) | `MatchDetailPanel`'s header, where one match owns the page    |

`sm` **extends** `game-asset-tokens.md`'s per-component mapping by one step (that table names
`icon-2xl` and `icon-3xl` only). It introduces no token and no new value: it exists so that a
thumbnail in a ruled table row stays inside the row's own text-driven height (§7), which is a
legibility requirement, not a size preference. The mapping table there carries a note pointing here.

**Sizes come from `iconTokens` / `--ds-icon-*`, never from a Tailwind size utility** — the generator
maps no Tailwind namespace onto this family (`build-tokens.mjs`'s own note), so `w-16` is a
hard-coded value even where it equals the token.

The box is **square** at every size. The pack's minimaps are square; a non-square source is
letterboxed by `object-fit: contain` and **never** stretched or cropped — a distorted minimap is a
different map's shape, which is worse than no image at all.

## 4. States

- **default** — framed thumbnail, then the name.
- **hover** — none of its own. The enclosing `MatchRow` link owns the row hover fill
  (`match-history.md` §5); the thumbnail does not zoom, lift, brighten or reveal a larger preview. A
  hover-only enlargement would hide the map from every touch and keyboard reader
  ([`README.md`](./README.md) rule 4's spirit and the repo's own note that snapshots are blind to
  hover).
- **focus-visible** — none. Not a tab stop, no `tabindex`; the row's link is the single focus stop.
- **active** — none.
- **disabled** — never. A map is a fact about a finished match; there is nothing to disable, and a
  dimmed minimap would read as "unavailable", a claim nobody made.
- **loading** — no loading state of its own. The caller renders `Skeleton/block` at the frame's exact
  footprint (`icon-lg` / `icon-2xl` / `icon-3xl` square, `radius-md`) beside a `Skeleton/text` at the
  name's width, so the loaded frame does not reflow. Never a spinner inside the frame, never a frame
  waiting for an image.
- **error** — the URL resolved but the image fails to load or decode: `onError` removes **the image
  and its frame together**, leaving the name alone — byte-identical to the `undefined` render below.
  No broken-image glyph, no empty frame, ever.
- **empty** — two distinct absences, rendering differently because they are different facts:
  - **A named map the pack does not cover** (`thumbnailUrl === undefined`): the name alone, in
    `text-primary`, with no frame and no reserved space. The row simply has no picture. This is the
    expected render for every custom and tournament map and must not look like a failure.
  - **No map name at all** (`mapName` is `null` — the source recorded none; `MatchDetailPanel`'s
    `map: ReactNode | null`): no thumbnail, and §11.2's `UnresolvedIdentifier` treatment for the
    name — `type-identifier` (T531/research D7: mono family and `text-secondary` by the role's own
    contract), wording that says the fact is missing rather than presenting an empty gap. **No
    thumbnail is ever guessed** from a leaderboard, a mode or a
    neighbouring match.

## 5. Tokens used

Colour: `border` for the frame hairline — README's own rule for that token, "decorative separators
only, never a control boundary", is exactly what this is: the frame bounds a picture, it does not
bound a control and it carries no meaning of its own. (Contrast this with `PlayerColourSwatch`'s
`border-strong` frame, which _is_ meaning-bearing: it makes a pale fill perceivable, so it owes the
3:1 non-text floor.) `text-primary` for a resolved name; `text-secondary` + `mono` for the
unresolved case, both via `UnresolvedIdentifier` (§11.2 — no new token). The image is never tinted,
filtered or theme-adjusted.

Typography: `sans`, weight normal, at the size of the text the pair sits in (`sm` in a row, `md` in a
detail header).

Size: `icon-lg` / `icon-2xl` / `icon-3xl` (§3). Radius: `md` on the frame — one step above
`CivilisationIcon`'s `sm`, because a larger square needs a slightly larger corner to read as the
same family.

Elevation: none — no shadow behind a thumbnail that sits in a row of numbers (README rule 1). Motion:
none. No fade-in on decode, no cross-fade when a new page of matches replaces the list. Nothing to
reduce under `prefers-reduced-motion`.

Gaps in play: none.

## 6. Spacing

| Between                                     | Step      |
| ------------------------------------------- | --------- |
| Thumbnail to name (`sm`, inline)            | `space-2` |
| Thumbnail to name (`md`/`lg`, side by side) | `space-3` |

No outer margin; the caller's layout gap (`match-history.md` §7) positions the pair.

## 7. Responsive

- **375 / 768** — `md` (64px), leading the `MatchRow` card with the name beside it. A card whose map
  is uncovered keeps its content-driven height and simply has no picture; cards in one list may
  therefore differ in height, which is accepted — the card is already a variable-height block (its
  meta line wraps), and the alternative is an empty box, which rule 2 forbids.
- **1280** — `sm` (32px) inside the table's Map cell. **This is the reason `sm` exists**: 32px fits
  inside the row's own height budget (`space-3` padding-block plus one `sm` text line), so a row with
  a thumbnail and a row without one are the same height and the table's rhythm survives an uncovered
  map. A 64px image in every row would make the table twice as tall and put the numbers further
  apart, which is the trade README rule 1 settles against decoration.
- **Detail** — `lg` (96px) in the header at every viewport; it wraps above the header text at 375
  rather than shrinking.
- The pair never wraps between the thumbnail and its name at any size.

## 8. Accessibility

- The image is `<img alt="">` — decorative, because the visible name beside it is the accessible
  name. Never `alt="Arabia"` (a screen reader would say the map twice), never `alt="map"`.
- `width`/`height` from the size token, so space is reserved before decode: no layout shift.
  `loading="lazy"`, `decoding="async"` — a 30-row history must not block first paint on 30 minimaps.
- Non-interactive: no `tabindex`, no `title`, no hover-only affordance. WCAG 2.5.8's 44px target does
  not apply; if a call site ever links the pair, the link's hit area is at least `icon-xl` (44px).
- Contrast: the name is `text-primary` on `surface` (15.3 light / 13.3 dark) or, unresolved,
  `text-secondary` on `surface` (6.2 / 7.8) — both from README's measured table, both AA. The
  minimap itself carries no contrast obligation, because it carries no information the name does not.
  The `border` hairline is decorative and is therefore exempt from 1.4.11, which is precisely why it
  may be `border` and not `border-strong`.
- The map name is selectable text and is never baked into the image.

## 9. Visual acceptance criteria

- [ ] Every story renders the map name. **No story shows a thumbnail with no name.**
- [ ] The uncovered-map story (`thumbnailUrl` undefined) shows the name alone: **no frame**, no grey
      box, no "?" tile, no reserved gap. Beside a covered story in the same frame, the two names sit
      on the same baseline.
- [ ] The failed-image story is **pixel-identical** to the uncovered-map story — the two screenshots
      overlay with no difference, frame included (that is, neither has one).
- [ ] No broken-image glyph in any story, either theme; no request under `/game-assets/maps/` returns
      404 (SC-005).
- [ ] The 1280 table story shows rows with and without a thumbnail at the **same row height**, in one
      screenshot.
- [ ] `sm`, `md` and `lg` in one frame are three visibly different sizes; every one is square and
      undistorted, and none is blurred at 2× device pixel ratio.
- [ ] The null-map story shows `UnresolvedIdentifier` wording in `type-identifier` and no
      image — visibly distinct, in the same frame, from a resolved name with no thumbnail (§11.2's
      distinction between "we have no picture" and "we have no map name").
- [ ] Greyscale: the map is still identified by its name in every story.
- [ ] The loading story's skeleton overlays the default story with no reflow of the name.
