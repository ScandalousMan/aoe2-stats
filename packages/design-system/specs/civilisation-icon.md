# CivilisationIcon

**Component**: `src/components/CivilisationIcon/` (T429)
**Feature**: 004, US1 — consumed by `MatchRow` and `MatchDetailPanel`
([`match-history.md`](./match-history.md) §12), themselves consumed by
`apps/web/src/routes/matches.index.tsx`, `matches.$gameId.tsx` and
`players.$profileId.matches.tsx`.
**Requirements**: FR-001, FR-010, FR-013. SC-001, SC-005.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — the `icon` size family (DS-7,
closed). [`shared-primitives.md`](./shared-primitives.md) — `Skeleton`, for the caller's loading
footprint.
**Asset origin** (README rule 3): the mark is a file in `packages/game-assets/civilisations/`, whose
`LICENCE.md` records source, licence, permitted usage, ruling and check date
(`specs/004-visual-parity/contracts/asset-pack.md`, enforced by `scripts/checks/asset_packs.py`).
**This component never imports it.** It receives a URL as a prop and knows nothing about packs,
which is what keeps the design system asset-agnostic and its unit tests free of binary fixtures
(plan.md, Structure Decision).

## 1. Purpose

Let a reader tell which civilisation a player played at a glance, from the game's own mark shown
beside the civilisation's name — so nobody has to decode a `civ_id`, and nobody has to recognise an
emblem they have not learned yet.

## 2. Anatomy

```
CivilisationIcon                  one inline group; the mark and the name are a single unit
├─ Mark        <img>, square, from `iconUrl`. ABSENT — not a placeholder — when `iconUrl` is
│              undefined (§4 empty). Never the only thing rendered.
└─ Name        the civilisation name, always rendered, always selectable text
```

**The component's name says "Icon"; what it renders is the mark _and_ the name.** The pair is the
unit because the mark alone is not permitted to carry the fact (README rule 4). The component name
is fixed by T429 and by the directory it lives in; read it as "the civilisation mark", of which the
image is one half.

Three rules govern this component, `MapThumbnail` and `PlayerColourSwatch` alike. They are stated
once in [`match-history.md`](./match-history.md) §12.1 and restated here only where they decide
something in this file:

1. **Colour — and imagery — is never the only carrier of meaning.** There is no `iconOnly` and no
   `labelHidden` prop. Adding one is a spec change, not an implementation choice: an emblem grid
   with no names is a memory test, and this is a data tool.
2. **The absent-asset state is the prop being `undefined`**, rendering the readable label alone.
   Never a placeholder image, a silhouette, a "?" tile or a reserved empty box — a placeholder is a
   broken image with better manners: it occupies the same space, teaches the reader nothing, and
   defeats the one check FR-010 is actually testable by (zero requests under `/game-assets/` that
   404 — `civilisationIcon()` returns `undefined` precisely so that nothing is requested).
3. **The name is resolved upstream, never here.** Feature 002's mapping answers for every integer —
   a known name, or `Civilisation {id}` — so `civ_name` is always present when `civ_id` is
   (`contracts/http-api.md`). This component formats no identifier and looks nothing up.

## 3. Variants and sizes

No tone or style variants: a civilisation is a fact, and a fact has one appearance.

| Size             | Token            | Where                                                           |
| ---------------- | ---------------- | --------------------------------------------------------------- |
| `md` _(default)_ | `icon-md` (24px) | `MatchRow`, at every viewport — the common case, read in a list |
| `lg`             | `icon-lg` (32px) | `MatchDetailPanel`'s participants, where one match has the page |

These are `game-asset-tokens.md`'s per-component mapping, not a new decision. **Sizes are consumed
from `iconTokens` / `--ds-icon-*`, never from a Tailwind size utility**: `build-tokens.mjs`'s own
note records that no Tailwind namespace maps this family onto `w-*`/`h-*`/`size-*`, so an
implementer typing `w-6` has hard-coded a value (constitution VI) even though it happens to equal
the token today. Below `icon-md` the emblems stop being recognisable, so the component has no
smaller size and never shrinks responsively (§7).

## 4. States

- **default** — mark then name, as tabled in §2.
- **hover** — none of its own. The enclosing `MatchRow` is a single link and owns the hover fill
  (§5 of `match-history.md`); the mark does not brighten, scale, lift or gain a ring. It is a fact,
  not a control.
- **focus-visible** — none. The image is never a tab stop and carries no `tabindex`; the row's own
  link is the single focus stop (`match-history.md` §9).
- **active** — none, for the same reason.
- **disabled** — never. A civilisation played in a finished match cannot become unavailable, and a
  dimmed emblem would read as "this data is stale", which is a different and false claim. If a
  caller wants to de-emphasise a whole row, it dims the row, not this component.
- **loading** — the component has no loading state of its own, and must never render half of itself.
  The caller renders `Skeleton/block` at the mark's exact footprint (`icon-md` or `icon-lg` square,
  `radius-sm`) beside a `Skeleton/text` at the name's width, so the loaded frame does not reflow
  (`match-history.md` §5's existing rule for the row extends to this pair). Never a spinner, never
  the name with an empty box beside it.
- **error** — `iconUrl` resolved but the image fails to load or decode (a pack file removed, a stale
  build, an offline cache): the `onError` handler removes the mark, and the name alone remains —
  **byte-identical to the `undefined` render below**. A broken-image glyph must never reach the
  screen. This is the same identical-render discipline `profile-summary.md` (T435) applies to a
  stale avatar hash: the two absences a viewer cannot act on differently must not look different.
- **empty** — two distinct absences, which do **not** render the same way:
  - **No mark for a known name** (`iconUrl === undefined`): the name alone, in the same
    `text-primary` a covered civilisation's name uses. This is the designed path for an expansion
    civilisation outside the shipped pack (spec.md's own edge case), not a defect — so it carries no
    apology, no dimming, no tooltip and no reserved gap. Nothing about the row tells the reader that
    an image was expected.
  - **No name at all** (`name` absent or blank — a contract violation upstream, since the API
    guarantees `civ_name` whenever `civ_id` is present): render the literal **"Unknown civilisation"**
    — `apps/web/src/features/matches/format.ts`'s existing wording, never a new phrase for the same
    gap — **and suppress the mark**. An emblem this component cannot name is a picture standing in
    for a fact, which is exactly README rule 4's failure mode.

## 5. Tokens used

Colour: `text-primary` (the name, in a row's primary line and in the participants table);
`text-secondary` when the caller places the pair inside a secondary metadata line (`MatchRow`'s
375 meta line — the caller's context decides, and the component inherits `currentColor` rather than
setting a colour of its own). No colour is applied to the mark: a pack image is shown as authored,
never tinted, filtered or theme-adjusted (README rule 6 — a component never branches on the theme,
and a tint would also alter a licensed asset).

Typography: `sans`, weight normal, at the size of the text the pair sits in (`sm` in a match row and
in the participants table, `md` in a detail header). The name never uses `mono`: it is prose, not an
identifier (DS-8's own distinction, and §11.2's reason for giving `UnresolvedIdentifier` the
opposite treatment).

Size: `icon-md` / `icon-lg` (§3). Radius: `sm` on the mark — a hairline softening that keeps a
square emblem from reading as a hard-edged sticker, matched by `MapThumbnail`'s own frame.

Elevation: none. Motion: **none at all** — no fade-in on decode, no scale on load. README rule 1:
nothing animates beside a number, and an image that fades in delays the read it exists to speed up.
Under `prefers-reduced-motion` nothing changes, because there was nothing to reduce.

Border: none. The pack's emblems are opaque squares with their own internal contrast, so a frame
would be decoration competing with `PlayerColourSwatch`'s frame, which is meaning-bearing there
(it makes a pale fill perceivable) rather than ornamental. **A pack whose images are transparent is
re-cut at pack time, never framed at render time** — that keeps the rule "a frame means something"
true across all five marks.

Gaps in play: none. DS-7 is closed by the `icon` family this component consumes.

## 6. Spacing

| Between      | Step      |
| ------------ | --------- |
| Mark to name | `space-2` |

That is the whole spacing surface. The pair adds no outer margin; the caller's own layout gap
(`match-history.md` §7) positions it.

## 7. Responsive

- **375 / 768 / 1280** — the mark's size is set by the caller's context (`md` in a row, `lg` in
  detail), never by the viewport. It does not shrink on a narrow screen: below `icon-md` the emblems
  become smudges, and a mark too small to recognise is decoration with a download cost.
- The pair **never wraps between the mark and its name**. If the container is too narrow, the name
  wraps within itself and the mark stays on the first line — the mark is never orphaned onto a line
  of its own, where it would momentarily be an image with no label.
- At 200% zoom the mark scales with the token (rem-based), so it grows with the text rather than
  staying a fixed pixel square beside doubled type.

## 8. Accessibility

- The mark is `<img alt="">` — **decorative**, because the accessible name is the visible text
  immediately beside it. Never `alt="Britons"`: that makes a screen reader announce the civilisation
  twice in a row, and never `alt="civilisation icon"`, which names the widget rather than the fact.
- `width`/`height` attributes (or an equivalent CSS aspect box) are set from the size token so the
  image reserves its space before it decodes — no layout shift, which is the same reflow rule §4's
  loading state states from the other side. `loading="lazy"` and `decoding="async"`: a long history
  list must not block first paint on 30 emblems.
- Not focusable, no `title`, no tooltip. The component is non-interactive, so WCAG 2.5.8's 44px
  target does not apply. If a call site ever wraps the pair in a link, that link's hit area is at
  least `icon-xl` (44px) — the reason that token is fixed at 44 rather than sitting on the space
  scale (`game-asset-tokens.md`, Decision 2).
- Contrast: the name is `text-primary` on `surface` — 15.3 light / 13.3 dark (README's measured
  table), well clear of AA. The image carries **no** contrast obligation, because it carries no
  information the adjacent text does not; that is a consequence of rule 4, not an exemption from
  1.4.11.
- The name is selectable text, never baked into the image (`match-history.md` §9's rule for figures,
  extended to this label).

## 9. Visual acceptance criteria

- [ ] Every story renders a name. **No story anywhere shows the mark without its name beside it** —
      including the size stories and the combined row story.
- [ ] The uncovered-civilisation story (`iconUrl` undefined) shows the name alone: no box, no
      silhouette, no "?" tile, no dimming, and no gap where the mark would be. Placed beside a
      covered story in the same frame, the two names sit on the same baseline and the only visible
      difference is the presence of the mark.
- [ ] The failed-image story (`iconUrl` set to a URL that does not resolve) is **pixel-identical** to
      the uncovered-civilisation story — the two screenshots overlay with no difference.
- [ ] No broken-image glyph appears in any story, in either theme; the browser network panel shows
      no request under `/game-assets/civilisations/` returning 404 (SC-005).
- [ ] The `md` and `lg` stories in one frame are visibly different sizes, both crisp at 1× and 2×
      device pixel ratio, and neither is distorted from square.
- [ ] Converting any story to greyscale leaves the civilisation identifiable, because the name is
      doing the work (README rule 4).
- [ ] The loading story's skeleton pair (block + text) overlays the default story with no reflow of
      the name's position.
- [ ] The blank-name story renders "Unknown civilisation" and **no mark**, in both themes.
