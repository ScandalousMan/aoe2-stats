# PlayerColourSwatch

**Component**: `src/components/PlayerColourSwatch/` (T429)
**Feature**: 004, US1 — consumed by `MatchRow` and `MatchDetailPanel`
([`match-history.md`](./match-history.md) §12).
**Requirements**: FR-003, FR-010, FR-013. SC-001, SC-005.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — Decision 1 (the eight
`player-N` / `player-N-contrast` tokens, landed by T410) and Decision 2 (the `icon` family).
[`README.md`](./README.md) — the measured "Player colour swatches" contrast table.
**Asset origin** (README rule 3): **none — this component renders no asset.** A player colour is
eight token values, not a bitmap; nothing is fetched, so nothing can 404 and the constitution X
licence gate has no surface here. That distinction matters in §4.

## 1. Purpose

Show which in-game colour a player used, as a chip beside their name, so a reader can tie a name in
the list to the colour they saw in the game — and so a team's players can be told apart at a glance
without reading every alias.

## 2. Anatomy

```
PlayerColourSwatch                the chip only — the name is the caller's, and is mandatory (§2a)
├─ Chip           a square, `border-strong`-framed fill: `player-1`…`player-8`, or `surface-sunken`
│                 when the colour is not recorded (§4 empty)
└─ ColourName     visually hidden text: "Colour: Blue" … "Colour: Orange", or
                  "Colour: not recorded" — the chip's meaning, in words, for assistive tech
```

Two elements, never more. **The component does not render the player's name**, because at every call
site the name is already on screen — the row's alias, the participants table's `<th scope="row">` —
and rendering it twice would put the same alias in the same line twice.

### 2a. The chip never renders without a name beside it

README rule 4 states it as a fixed example: "a `PlayerColourSwatch` always sits beside the player's
name." Two mechanisms keep it true rather than hoped for:

- **`playerName` is a required prop**, and **the component renders `null` when it is blank.** A chip
  with no name to sit beside must not exist; nothing is lost by omitting it, because the row it would
  have sat in has no name either.
- **Placement is fixed by the consumer's spec, not chosen per call site**:
  [`match-history.md`](./match-history.md) §12.3 puts the chip immediately before the alias, in the
  same line or the same table cell — never in a column of its own. A colour column would put the chip
  a column away from the name it describes and invite reading it as a standalone status.

## 3. Variants and sizes

No tone variants — the fill is decided entirely by `colorId` (§4's table), never by the caller. A
call site cannot pass a colour, which is what stops two views of the same match from disagreeing
about a player's colour (the same discipline `CaptureStateBadge` §4 uses for its tone).

| Size             | Token            | Where                                                                                 |
| ---------------- | ---------------- | ------------------------------------------------------------------------------------- |
| `xs` _(default)_ | `icon-xs` (12px) | `MatchRow` — the densest case, where up to eight chips can appear in one row          |
| `sm`             | `icon-sm` (16px) | `MatchDetailPanel`'s participants table, and the **only** size that may carry a glyph |

Both are `game-asset-tokens.md`'s per-component mapping. Sizes come from `iconTokens` /
`--ds-icon-*`, never from a Tailwind size utility (`build-tokens.mjs`'s own note).

**No glyph in the chip in this feature.** The eight `player-N-contrast` tokens exist so that a future
mark (a winner tick, say) can sit on a fill without anyone hand-picking a black or a white; any
component that ever does so uses `sm`, uses `player-N-contrast`, and clears the 4.5:1 already
asserted for that pair. Feature 004's winner signal is a word, not a glyph
([`match-history.md`](./match-history.md) §12.3), so no chip carries one today.

## 4. States

- **default** — the chip, filled per this table, framed 1px in `border-strong` in both themes:

  | `colorId` | Fill token | Hidden text      |
  | --------- | ---------- | ---------------- |
  | 1         | `player-1` | "Colour: Blue"   |
  | 2         | `player-2` | "Colour: Red"    |
  | 3         | `player-3` | "Colour: Green"  |
  | 4         | `player-4` | "Colour: Yellow" |
  | 5         | `player-5` | "Colour: Teal"   |
  | 6         | `player-6` | "Colour: Purple" |
  | 7         | `player-7` | "Colour: Grey"   |
  | 8         | `player-8` | "Colour: Orange" |

  The names are the game's own slot names, matching `game-asset-tokens.md`'s token table exactly —
  the mapping is stated in one place and read here, never re-derived from a hex value.

  **The colours are theme-invariant** (`game-asset-tokens.md`, Decision 1): a player's colour is
  their identity, so Blue is the same Blue in both themes, and the frame — not a per-theme re-tint —
  is what keeps a pale fill perceivable against light parchment.

- **hover** — none of its own. The enclosing row link owns the hover fill; the chip does not grow,
  glow or gain a ring. It is a fact, not a control.
- **focus-visible** — none. Never a tab stop, no `tabindex`.
- **active** — none.
- **disabled** — never. Nothing about a finished match's colours can be disabled, and a dimmed chip
  would read as a ninth colour.
- **loading** — the component has no loading state of its own, and **must never render a neutral chip
  as a "loading colour"**. A grey chip that later flips to Blue is a false statement for as long as
  it is on screen. While a row is loading, the row's own skeleton covers this position
  (`match-history.md` §5); no swatch renders at all.

  Related, and deliberate: `color_id` is filled in by a read-time enrichment
  (`data-model.md` §6), so a chip that is neutral on one view can be coloured on the next. That flip
  is **instantaneous** (`motion.duration.instant`) — never a cross-fade, which would draw the eye to
  a change the reader did not ask about.

- **error** — `colorId` present but outside `1..8` (a value neither this service nor the game
  defines): the **same** neutral chip and the same "Colour: not recorded" text as the empty state
  below. Never a red chip, never an error tone, never nothing. To a reader, a colour we cannot name
  and a colour nobody recorded are the same fact, and rendering them differently would invite a
  distinction they cannot act on.
- **empty** — `colorId` is `null`: a `surface-sunken` fill inside the same `border-strong` frame,
  with hidden text "Colour: not recorded". This is `game-asset-tokens.md`'s ratified neutral case and
  a **legitimate resting state**, not a migration in progress: a match companion has never heard of
  keeps `color_id` NULL permanently (`data-model.md` §6), and the view is still correct.

### Why a neutral chip is not the placeholder image FR-010 forbids

[`match-history.md`](./match-history.md) §12.1's third rule — the absent-asset state is the prop
being `undefined`, rendering the label alone, never a placeholder — governs **image props**
(`iconUrl`, `thumbnailUrl`). It does not govern this one, and the difference is not a loophole:

- **Nothing is fetched.** There is no URL, no request, no 404, and therefore no broken image to have
  better manners about. The neutral fill is a real token with a real meaning, not a stand-in graphic.
- **The absence is stated in words**, in the same element, to assistive tech: "Colour: not recorded".
  A placeholder image states nothing.
- **It keeps a column of names aligned** where a collapsed chip would ripple every alias in a
  participants table left by 12px on the rows that happen to lack a colour — a legibility cost paid
  by every row to mark one (README rule 1).

## 5. Tokens used

Colour: `player-1` … `player-8` (fills), `surface-sunken` (the not-recorded fill), `border-strong`
(the 1px frame, both themes), `player-1-contrast` … `player-8-contrast` (reserved for a glyph; unused
in this feature, §3). **No hex string appears in this component** — T429's own acceptance includes
that the file contains none.

Size: `icon-xs` / `icon-sm`. Radius: `sm` — a softened square. Not `full`: a circle reads as a status
dot (a thing that can change), and this is an attribute of a finished match. Not `none`: a hard
square at 12px reads as a rendering artefact beside rounded type.

Elevation: none. Motion: `motion.duration.instant` for the neutral→coloured transition described in
§4's loading note; nothing else moves, so `prefers-reduced-motion` changes nothing.

Contrast: README's "Player colour swatches" table carries all eight `-contrast` pairs (4.5:1 floor,
asserted in `tokens/build-tokens.test.mjs`). The frame's own pairs — `border-strong` on `surface`
(3.5 light / 3.8 dark) and on `surface-raised` (3.4 both) — are already in that table and already
asserted; this component adds no new pair.

Gaps in play: none.

## 6. Spacing

| Between                                 | Step      |
| --------------------------------------- | --------- |
| Chip to the alias it belongs to         | `space-2` |
| Between two swatch+alias pairs in a row | `space-3` |

Both are set by the consumer (`match-history.md` §12.7); the component itself adds no margin, so it
can be dropped into a table cell without shifting the cell's text.

## 7. Responsive

- The chip is **the same size at 375, 768 and 1280** (`xs` in a row, `sm` in the participants table).
  It does not grow on touch: it is not a target, and enlarging it would make it compete with the
  aliases it annotates.
- The chip and its alias **never wrap apart**. When a row's participant list wraps, it wraps between
  pairs, never between a chip and the name it belongs to — a chip alone at the start of a line is a
  colour with no owner.
- At 200% zoom the chip scales with the token (rem-based), keeping its proportion to the alias beside
  it.

## 8. Accessibility

- The chip is a decorative element (`aria-hidden`), and the meaning travels as **real text**: a
  visually hidden `<span>` immediately after it, reading "Colour: Blue" or "Colour: not recorded".
  Never an `aria-label` on a bare `<div>` and never `title` — the same rule `CaptureStateBadge` §11
  states ("never an `aria-label` standing in for visible text"), satisfied here by hidden text that
  is genuinely in the reading order.
- Reading order inside a participants table cell is therefore "Colour: Blue" then the alias. That is
  the order the chip is drawn in, so a sighted and a screen-reader user get the same two facts in the
  same order.
- The frame is what makes a pale fill (Yellow, Green, Teal) perceivable against light parchment and
  therefore **is** a meaning-bearing non-text boundary: it owes WCAG 1.4.11's 3:1 and meets it via
  `border-strong` (README table), in both themes.
- **Colour is never the only carrier**: the fill is redundant with the adjacent name and with the
  hidden text. A reader who cannot distinguish Green from Teal loses nothing they need — which is why
  §2a's "no name, no chip" rule is a hard one.
- Non-interactive, so WCAG 2.5.8's 44px target does not apply. A call site must not make the chip
  itself a control; if a colour ever becomes a filter, the control is a labelled button that contains
  the chip, sized to at least `icon-xl`.

## 9. Visual acceptance criteria

- [ ] A story rendering all eight colours in one frame shows eight visibly distinct chips, **each
      beside a name**, in both light and dark theme — and each chip is identical between the two
      themes (theme-invariance is visible by overlaying the two screenshots).
- [ ] Every chip in every story has a visible 1px frame, including Yellow, Green and Teal on the
      light theme's parchment — no chip dissolves into the background.
- [ ] The `colorId: null` story and the `colorId: 99` (out-of-range) story are **pixel-identical**.
- [ ] Neither of those two stories uses `danger`, `warning` or any error affordance, and neither
      collapses: the chip is present, neutral, and the aliases beside it stay aligned with the rows
      above and below (place a coloured and a neutral row in one frame to check the alignment).
- [ ] **No story shows a chip without a name beside it in the same line or cell** — including the
      all-eight-colours story, which names its rows.
- [ ] The blank-`playerName` story renders nothing at all where the chip would be.
- [ ] Converting any story to greyscale leaves every player identifiable by name, and the chips
      become indistinguishable — which is the point: nothing was riding on the colour alone.
- [ ] No hex string appears in `PlayerColourSwatch`'s source (greppable; T429's own check), and the
      chip sizes resolve from `--ds-icon-xs` / `--ds-icon-sm` rather than a utility class.
