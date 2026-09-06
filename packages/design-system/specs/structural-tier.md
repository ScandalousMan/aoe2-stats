# The structural tier

**Components**: `src/primitives/{Page,Section,Panel,Text,Link,Table,Field,EmptyState,ErrorState}/`
(T543–T548; the directory is `primitives/` after T540's tier move, never `components/`).
**Feature**: 005, US2.
**Requirements**: FR-008, FR-012, FR-013, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-024,
FR-025, FR-026, FR-028, FR-029, FR-035, FR-037, FR-038, FR-050, FR-053, FR-054, FR-055, FR-056,
FR-059, FR-063. SC-003, SC-004, SC-009, SC-013.
**Contract**: [`specs/005-design-system-foundations/contracts/structural-tier.md`](../../../specs/005-design-system-foundations/contracts/structural-tier.md)
fixes what each primitive **owns** and what it **forbids its caller**. This file is the visual
specification of the same nine — anatomy, states, tokens, spacing, responsive behaviour,
accessibility and the acceptance criteria `visual-reviewer` judges against. Where the two touch, the
contract decides ownership and this file decides appearance; neither restates the other.
**Depends on**: [`README.md`](./README.md) — the measured contrast table (referenced by pair, never
by number), the elevation meanings, the iconography contract, the two surface classes and the eight
standing rules. [`tokens/space.json`](../tokens/space.json) — the `rhythm` group §2 assigns.
[`contracts/token-families.md`](../../../specs/005-design-system-foundations/contracts/token-families.md)
§2 — the utility vocabulary a primitive may write, and nothing else.
**Tier**: all nine are **primitives**. None carries domain knowledge, none imports a composite or a
screen, and none imports from `apps/` (FR-028, FR-029, enforced by `scripts/checks/tier-deps.mjs`).
**Asset origin** (README rule 3): **none — not one of the nine renders an asset.** No icon, no
portrait, no screenshot, no bitmap of any kind: the structural tier draws boxes, rules and text from
tokens. `Link`'s external mark (§9) is an inline path drawn from `currentColor`, original to this
repository, not a licensed glyph. The constitution X gate therefore has no surface here, and a
future change that gives any of these nine an image prop acquires one.

---

## 0. How to read this file

Nine primitives, each carrying the nine mandated sections in compressed form — the shape
[`shared-primitives.md`](./shared-primitives.md) already uses, for the same reason: the nine agree
with each other more than they differ, and specifying them apart is how they drift.

Three facts are shared by all nine and are stated **once**, in §2, §3 and §4, then referenced. A
number written twice goes stale in one copy, and the rhythm rule in particular exists precisely
because the same relationship was expressed three different ways in seven files.

**The state vocabulary in force when this file was written is the eight**: default, hover,
focus-visible, active, disabled, loading, error, empty. Every primitive below answers all eight,
including the refusals. T569 extends the vocabulary to ten by adding **selection** and **expansion**;
none of these nine implements either today — no primitive here is selectable and none collapses —
so when T569 lands, its amendment to this file is nine answers of "inapplicable, and here is what
happens instead", not a redesign. Recorded now so the next reader does not mistake the omission for
an oversight.

**Hover, focus-visible and active are not decidable from a static story capture.** The suite
screenshots stories at rest; it cannot force a pointer or a focus ring. Every criterion below that
names one of those three states is decided from an **interaction test's** capture
(`tests/visual/focus-ring.spec.ts` is the shipping precedent), and a criterion phrased so that only
a static baseline could answer it would be undecidable in exactly the way FR-059 forbids. This is
stated here rather than nine times.

---

## 1. What the tier is for, and the boundary against what already exists

A screen is assembled from these nine, so the application writes no layout and no spacing (FR-021).
Two boundaries are load-bearing and are stated before the specifications, because a primitive
admitted for a job an existing component already does is the drift FR-030 exists to stop:

- **`ErrorState` is not `Callout`.** A `Callout` explains an outcome **beside content that is still
  there** — the favourites list that failed to update is still on screen and still readable.
  `ErrorState` **replaces the content that failed**, because there is nothing left to read. A route
  whose request failed renders `ErrorState`; a route whose secondary action failed renders a
  `Callout` above content that still renders. Choosing wrongly is visible in a screenshot: an
  `ErrorState` with a populated table under it is the defect.
- **`EmptyState` is not `Skeleton`.** A `Skeleton` says _arriving_; an `EmptyState` says _settled,
  and there is nothing_. They must never be ambiguous in a still image, which is why `EmptyState`
  always carries a sentence and `Skeleton` never carries text (README rule 1 and
  `shared-primitives.md`'s `Skeleton`).

Both boundaries are also what keeps the eight repeated error presentations in the application from
becoming nine slightly different ones.

---

## 2. The rhythm rule, assigned (FR-008, T520, closes the drift spec.md names)

`tokens/space.json`'s `rhythm` group names three relationships and this file assigns each one a
concrete step from that file's own `scale`. **These three steps are the whole of the system's
vertical rhythm.** Nothing else expresses a relationship between things on a page, and the
application cannot express any of them at all, which is what makes this a rule rather than a habit.

| Relationship           | Step               | Expressed by                     | Grounded in                                                                                                 |
| ---------------------- | ------------------ | -------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Within a component** | `space-2` (0.5rem) | the component's own internal gap | the majority `gap-2` across every icon/text and label/value pairing in the package                          |
| **Between components** | `space-6` (1.5rem) | `Section`'s internal stack gap   | `match-history.md`'s documented "page header to match list — `space-6`", used identically in two containers |
| **Between sections**   | `space-8` (2rem)   | `Page`'s section rhythm          | `replay-availability.md` §8 and `analysis-timeline.md` §7, which already name this relationship in words    |

**The three steps do not change with viewport width.** A rhythm that opens at a breakpoint cannot be
compared between two routes at a single width, and SC-004's test — a new route's rhythm matches an
existing route's _without adjustment_ — is exactly that comparison. Page **padding** is responsive
(§5); page **rhythm** is not. The two are different decisions and are kept apart deliberately: one
is the distance from the content to the edge of the glass, the other is the distance between two
ideas.

**Why `space-8` and not `space-12`.** `gap-12` appears once in the application with no rationale
recorded anywhere, and it is the value this rule retires. Between-sections must be visibly larger
than between-components at every width — that is the whole point — and one step of the scale
(`space-6` → `space-8`, 24px → 32px, a third again) reads as a larger break without pushing a data
tool's third section below the fold on a laptop. Information density outranks air (README rule 1).

**A fourth relationship exists and is not rhythm**: the distance from a surface's edge to its own
content. That is padding, it is decided by the surface class, and it lives in §3.

---

## 3. Density applied: `dense` and `prose` on `Panel` and `Table` (FR-012)

[`README.md`](./README.md)'s "Surface density" section defines the two classes — their row height
and padding, their line rhythm, and the typography roles each may draw in. This section **applies**
those definitions to the two primitives that carry the class as a prop (`density`, T544 and T546),
and resolves the two questions the class definitions leave open for a bounded surface and for a
tabular one. It adds no third class and no new value: every step below is either quoted from that
section or derived from it, with the derivation stated.

| Surface                | `dense`                                                                    | `prose`                                                        |
| ---------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `Panel` padding        | `space-4`, at every width                                                  | `space-6` below `md`, `space-8` from `md`                      |
| `Panel` internal stack | `space-3` between stacked blocks                                           | `space-4` between paragraphs                                   |
| `Panel` text width     | unbounded within the panel                                                 | bounded to `max-w-measure`                                     |
| `Table` row padding    | `space-3` block padding per cell                                           | `space-4` block padding per cell                               |
| `Table` body type      | `type-numeric` (numeric columns), `type-machine`, `type-body` at `text-sm` | `type-body` at `text-md`, `type-supporting` for a footnote row |

**Where each value comes from.**

- `Panel` at `dense` pads `space-4` rather than the class's own `space-3`, because `space-3` is the
  class's **row** padding — the value every `<th>` and `<td>` in `MatchRow` carries — and a bounded
  surface's edge is not a row boundary. `space-4` is the smallest step that keeps a hairline border
  from crowding the first line of text at 375px, and it is what `SignInScreen`'s and
  `MatchDetailPanel`'s blocks already read as. The internal `space-3` sits one step below
  `between-components` on purpose: a dense panel's children are rows of one thing, not two
  independently meaningful components, and using the `space-6` rhythm inside it would make a compact
  list read as a stack of sections.
- `Panel` at `prose` takes the class's own surface padding verbatim (`space-6` narrow, `space-8` from
  `md`) and its own paragraph rhythm (`space-4`), exactly as `PrivacyNotice`'s wrapper renders today.
  `max-w-measure` is the reading-measure token (`size.json`, DS-6); a prose panel that fills a 1280px
  page with a single line of text is a legibility defect even though every value in it is a token.
- `Table` at `dense` is the class's row padding unchanged, `space-3`.
- `Table` at `prose` has no row value in the class definition, because a prose surface's unit is the
  paragraph. It is derived, once, here: **`space-4`, the class's own paragraph step**, so a
  definitional table inside a legal notice breathes at the same rate as the paragraphs around it. No
  fourth value is invented.

**A component picks exactly one class when its spec is written — never both, never at the reader's
discretion** (README, and spec.md's assumption, quoted there rather than re-paraphrased here). The
seven primitives without a `density` prop do not have a surface to classify: `Page` and `Section`
draw no fill, `Text` and `Link` are ink, and `Field`, `EmptyState` and `ErrorState` inherit the class
of whatever surface they are placed on.

---

## 4. Rules every one of the nine obeys

Stated once here; not repeated in the nine specifications below.

1. **No primitive branches on the theme** (README rule 6). Both themes are served by the same token
   names and every pair each primitive paints is in the measured contrast table, referenced by pair.
2. **No primitive draws a shadow except by the elevation meanings** in README's elevation section.
   `Page`, `Section`, `Panel`, `Text`, `Link`, `Table`, `Field`, `EmptyState` and `ErrorState` all
   draw `elevation none`. The one `raised` surface in the system stays where README already records
   it, and §7 explains why `Panel` has no elevation prop.
3. **No transition longer than `motion.duration.fast`, and no motion carries meaning alone**
   (FR-010). Under `prefers-reduced-motion: reduce` every transition is `motion.duration.instant`
   and no loop runs (README rule 5).
4. **No texture, gradient, glow or border ornament behind or across a number**, and no number
   animates on entry (README rule 1). This is the rule that decides `Table` has no zebra striping
   (§10) and that `EmptyState` carries no illustration (§12).
5. **Nothing here is enlarged by a transparent overlay** to reach a touch target (FR-056). Where a
   primitive contains a control, the control's own box or its own padding reaches 44px.
6. **Every one of the nine renders nothing at all rather than an empty box.** A bordered rectangle
   with no content is the state that ships by accident; `Callout` already answers it this way and
   the nine follow.

---

## 5. `Page`

**Purpose** — give a route the one main landmark, the one content width and the one page padding it
must not decide for itself, so two routes are structurally indistinguishable without anyone
comparing them.

**Anatomy**

```
Page                       <main id="main-content" tabIndex={-1}> — the route's only landmark
└─ ContentColumn           centred, max-width from the width vocabulary below, page padding
   ├─ PageHeader           title (the page's only <h1>) / optional description / optional action row
   └─ SectionStack         the route's Sections, separated by the between-sections step
```

`PageHeader` is not optional and `title` is a required prop. A page with no `<h1>` is a page a
screen-reader user cannot orient in, and leaving the heading to each route is how the landmark
defect happened in the first place. A route whose title is already carried by a large visible
element passes `titleHidden`, which renders the same `<h1>` visually hidden — present in the
accessibility tree, absent from the picture. There is no third option.

**`Page` says `title`; `Section`, `Panel`, `EmptyState` and `ErrorState` say `heading` (FR-032,
T557, `packages/design-system/specs/README.md`'s rule 9).** These are not the same concept under
two names: a page has exactly one `title` — its `<h1>`, the document's own identity — and any
number of blocks inside it may each carry a `heading`, one level down. Calling both `heading` would
suggest a `Page` is one more block among the ones it contains, which is exactly the flattening the
landmark defect came from.

**Variants and sizes** — no variants. One prop shapes it, a closed three-value width vocabulary
drawn from `size.json`:

| `width`            | Token           | For                                                                        |
| ------------------ | --------------- | -------------------------------------------------------------------------- |
| `page` _(default)_ | `max-w-page`    | data views — tables, dashboards, match history                             |
| `panel`            | `max-w-panel`   | a single-column form or result column (`SearchContainer`'s existing 42rem) |
| `measure`          | `max-w-measure` | continuous reading — the privacy notice and every prose route              |

Three named tokens, chosen by the route's own spec; a route may not write a max-width class and may
not express a fourth width (FR-021). The vocabulary is three rather than one because forcing a
reading column or a search form to 80rem would produce a 200-character line, and line length is
legibility, which outranks uniformity (README rule 1).

**States**

- **default** — as above, on `background`.
- **hover / active** — none. A page is not a control.
- **focus-visible** — the landmark is the skip link's target and carries `tabIndex={-1}`. When the
  skip link sends focus to it, it shows the standard ring (`outline-ring`, `outline-offset-ring`,
  `focus-ring`) against `background`, the pair the README table already carries. It never shows a
  ring on a pointer click, which is what `focus-visible` means and why it is not `focus`.
- **disabled** — never. A page cannot be disabled; a route the reader may not use renders an
  `ErrorState` (§13) explaining why, inside a normal `Page`.
- **loading** — the header renders immediately and never waits for data: the title is known before
  the request resolves and withholding it costs the reader their orientation. The section stack
  carries `aria-busy="true"` **once for the whole region**, never per skeleton (FR-054, T532's
  rule), and holds `Skeleton`s. No full-page spinner, ever.
- **error** — the header is retained and the section stack is replaced by one `ErrorState`. Retaining
  the header is what keeps a failed route from looking like the wrong route.
- **empty** — a `Page` with a header and no sections renders the header plus one `EmptyState`. A
  padded, bordered, wordless column is the defect FR-023 names.

**Tokens used** — colour `background` (the page fill), `text-primary` (title), `text-secondary`
(description), `focus-ring` (the landmark's ring). Width `size.page` / `size.panel` / `size.measure`.
Typography `type-display` at `text-3xl`, weight `semibold`, `tracking-tight` for the title;
`type-body` at `text-md` for the description. Border widths `border.ring` / `border.ring-offset` for
the ring. Elevation `none`. Motion: none — a page does not animate in.

**Spacing**

| Between                          | Step                                      |
| -------------------------------- | ----------------------------------------- |
| Page edge to content, inline     | `space-4` below `md`, `space-6` from `md` |
| Page edge to content, block      | `space-6` below `md`, `space-8` from `md` |
| Title to description             | `space-2` (within a component)            |
| Page header to the first section | `space-6` (between components)            |
| Section to section               | `space-8` (between sections)              |

The padding values are the majority of what nine containers already write (`px-4 py-6 md:px-6
md:py-8`); this primitive is where they stop being written nine times.

**Responsive** — 375: padding `space-4` / `space-6`, content column full width. 768 and 1280:
padding `space-6` / `space-8`, content centred at the chosen width token. The width token and the
rhythm are identical at all three; only the padding steps. The page never scrolls horizontally at
any of the three widths (FR-018) — a wide `Table` scrolls inside itself (§10), it does not widen the
page.

**Accessibility** — exactly one `<main>` per rendered route, carrying `id="main-content"` and
`tabIndex={-1}` (FR-022, SC-003); counted by a check, not read from a screenshot. Exactly one `<h1>`,
which is `PageHeader`'s title. The skip link in `SiteHeader` targets this landmark and its obligation
is satisfied here, so no route can satisfy it wrongly. Focus order runs header → page content →
footer, matching the visual order.

**Visual acceptance criteria**

- [ ] Two different routes captured at the same width show the **same** left and right content edges
      and the same distance from the header to their first section — measurable by overlaying the
      two screenshots.
- [ ] At 375 the content clears the viewport edge by one small step and at 1280 by a visibly larger
      one; at no width does text touch the edge of the glass.
- [ ] No page screenshot at 375, 768 or 1280 has a horizontal scrollbar or content cut off at the
      inline-end edge of the viewport.
- [ ] The page's title is the largest and heaviest text in the frame, and nothing inside a section
      competes with it — a token-correct page whose section heading reads as large as its title
      fails this criterion (FR-063).
- [ ] The `titleHidden` story shows no title in the picture and the accessibility snapshot still
      names one `<h1>`.
- [ ] The loading story shows the title and skeletons — never a bare spinner and never an empty
      column.
- [ ] The error story shows the title, and where the sections were there is one `ErrorState`; no
      section content remains beneath it.
- [ ] The skip-link interaction test shows a visible ring around the content region after the skip
      link is activated, in both themes.

---

## 6. `Section`

**Purpose** — group one idea's worth of a page under a heading, and own the space between the
components inside it so no caller writes a margin.

**Anatomy**

```
Section                    <section aria-labelledby="…">
├─ SectionHeader           heading (h2, or h3 when nested) / optional description / optional action
└─ SectionBody             the section's components, stacked at the between-components step
```

**Variants and sizes** — no variants. **A `Section` always has a heading.** A region with no heading
cannot be labelled, and an unlabelled `<section>` is a landmark that announces nothing — worse than
a `<div>`. Where a heading would be visual noise, it is rendered visually hidden; that is the escape
hatch, and there is no headingless variant.

Heading level is derived from nesting depth, never passed: top level renders `<h2>` (the `<h1>` is
`Page`'s), one level of nesting renders `<h3>`. **A second level of nesting is forbidden**: a page
needing an `<h4>` is a page that should be two routes, and a level derived from depth cannot skip a
level the way a hand-passed one can.

**States**

- **default** — as above. No fill, no border, no radius: a `Section` is rhythm and a heading. A
  section that needs a bounded surface contains a `Panel`; it does not become one.
- **hover / active / focus-visible** — none of its own. Its heading is not a control and the section
  is not focusable; the components inside it carry their own.
- **disabled** — never. A section the reader may not act on keeps its heading and explains itself in
  words; greying out a whole region tells the reader nothing about why.
- **loading** — the heading renders immediately; the body carries `aria-busy="true"` once and holds
  `Skeleton`s. The heading never becomes a skeleton — the reader loses their place in the page for
  no benefit.
- **error** — the heading is retained, the body is replaced by one `ErrorState`. One failed section
  never removes the rest of the page.
- **empty** — the heading is retained, the body is replaced by one `EmptyState` with its sentence. A
  heading followed by nothing is the second most common form of the blank-region defect.

**Tokens used** — colour `text-primary` (heading), `text-secondary` (description). Typography
`type-display` at `text-2xl` (`h2`) / `text-xl` (`h3`), weight `semibold`, `tracking-tight` on `h2`;
`type-supporting` at `text-sm` for the description. No colour fill, no border, no radius, no
elevation, no motion.

**Spacing**

| Between                              | Step                           |
| ------------------------------------ | ------------------------------ |
| Heading to description               | `space-2`                      |
| Section header to body               | `space-4`                      |
| Component to component inside a body | `space-6` (between components) |

The header-to-body step sits between the two named rhythm steps deliberately: a heading belongs to
the body under it, so it must sit closer to that body than the body's own components sit to each
other, or the heading reads as floating between two sections.

**Responsive** — identical structure at 375, 768 and 1280. The header's optional action row sits
inline with the heading from `md` and wraps below it at 375, at `space-2`. The between-components
step does not change with width (§2).

**Accessibility** — a real `<section>` with `aria-labelledby` pointing at its heading, so the region
announces its own name. Heading levels descend by one and never skip. The optional action in the
header is a real `Button` or `Link` and is reached in the reading order after the heading, before
the body.

**Visual acceptance criteria**

- [ ] In a story with two sections, the gap between the last element of the first section and the
      heading of the second is **visibly larger** than the gap between two components inside either
      section — measurable in one screenshot, and the criterion a token-correct implementation that
      used one gap for both would fail (FR-063).
- [ ] The section heading is visibly smaller than the page title and visibly larger than any heading
      inside a `Panel` in the same frame.
- [ ] A heading and the description under it read as one block: their gap is visibly smaller than the
      gap from the description to the first component.
- [ ] The nested-section story shows exactly two heading sizes below the page title, and the inner
      heading is the smaller.
- [ ] The empty story and the error story both still show the section heading, with one `EmptyState`
      or one `ErrorState` beneath it.
- [ ] No section story draws a border, a fill or a shadow around itself.

---

## 7. `Panel`

**Purpose** — bound a block of related content on its own surface, so a reader can tell where one
unit of information ends and the next begins without a heading having to do all the work.

**Anatomy**

```
Panel                      the bounded surface: fill, hairline border, panel radius
├─ PanelHeader   optional  heading (h3 by nesting) / optional description / optional action
├─ PanelBody               the content, stacked at the density's internal step
└─ PanelFooter   optional  a summary line or an action row
```

**Variants and sizes** — no variants. One prop: `density`, taking `dense` or `prose`, whose values
are §3's. Size is intrinsic: a panel is as tall as its content and as wide as its column.

**Surface, and the one nesting rule.** A `Panel` on a page draws `surface`. A `Panel` nested one
level inside another draws `surface-raised`, so the inner block is distinguishable from the outer
one. **A second level of nesting is forbidden**: there is no third surface token that keeps its
distance from both, and a reader has stopped counting boxes by then. The nesting level is read from
context, never passed as a prop — a caller that could pass it could disagree with the page.

**Why `Panel` has no elevation prop.** The contract forbids the caller choosing an elevation and this
is where that becomes concrete: `Panel` always draws `elevation none`. README's elevation section
reserves `raised` for "the page's single focal surface" and names `SignInScreen`'s card as its one
call site — a claim about a whole screen, which a reusable bounded surface cannot make. A `Panel`
that could be lifted would be lifted twice on the same page within a month, and `raised` would stop
meaning anything. The panel is separated from the page by its fill and its hairline border, which is
enough, and which is what the parchment-and-rule character asks for anyway.

**States**

- **default** — fill `surface` (or `surface-raised` when nested once), `border-hairline` in `border`,
  `rounded-panel`, `shadow-none`.
- **hover** — none. **A `Panel` is never itself interactive**: no hover fill, no lift, no pointer
  cursor. A call site that needs a clickable card puts a real link inside the panel spanning its
  content, and that link owns the `surface-sunken` hover fill — the shape `MatchRow` already ships,
  and the reason modifier-clicks still work.
- **focus-visible** — none of its own; it is not focusable. Controls inside it carry their own rings,
  offset from the panel's border by `border.ring-offset` so a focused control at the panel's edge is
  not clipped by the panel's radius.
- **active** — none, for the same reason as hover.
- **disabled** — never. A panel whose content is unavailable says so in words; a greyed-out bordered
  box is a dead end with a frame around it.
- **loading** — the panel keeps its full frame, its radius and its padding and fills with
  `Skeleton`s matching the footprint of what is arriving; `aria-busy="true"` sits once on the panel,
  not on each skeleton. The frame must not collapse and re-expand — that reflow is exactly what the
  skeleton exists to prevent.
- **error** — the frame is retained and the body is replaced by one `ErrorState`. A panel that
  vanishes on failure takes the reader's context with it.
- **empty** — with a caller-supplied empty condition: the frame is retained and the body is one
  `EmptyState`. With **no children at all**: the panel renders nothing — no frame, no padding. The
  distinction matters, and it is `Callout`'s precedent applied: an empty bordered box is a defect,
  but a region the caller deliberately marked empty needs its words.

**Tokens used** — colour `surface`, `surface-raised` (nested once), `border` (the hairline),
`text-primary` (heading and body), `text-secondary` (description and footer), `surface-sunken` (only
as the hover fill of a link the caller places inside). Border width `border.hairline`. Radius
`rounded-panel` — the role, not a size; two panels of the same role cannot differ (FR-013). Elevation
`none`. Typography per §3's role table for the chosen class. Motion: none of its own.

**Spacing** — §3's table: padding `space-4` at `dense`, `space-6`/`space-8` at `prose`; internal
stack `space-3` at `dense`, `space-4` at `prose`; header to body `space-3`; body to footer `space-4`.
The panel adds no outer margin — the distance to whatever sits above it belongs to `Section`.

**Responsive** — full width of its column at every width. `dense` padding is identical at 375, 768
and 1280 (a dense surface is dense because the reader wants rows, not air). `prose` padding opens
from `space-6` to `space-8` at `md`, and a `prose` panel's text is bounded to `max-w-measure` at
every width, so it stops growing before the column does. A panel's radius never changes with width;
a card that flattens into a table row at a breakpoint is a composite making a structure decision
(FR-019), not a panel restyling itself.

**Accessibility** — a plain `<div>` unless it has a header, in which case it is a `<section>` with
`aria-labelledby` pointing at its heading. Never `role="region"` on an unlabelled panel: an
unnamed region is noise in the landmark list. The hairline border is decorative — the fill change
carries the boundary — so it owes no 3:1, and the `border` pairs in the README table are recorded as
decorative for exactly this reason. A `prose` panel's line length is bounded by `max-w-measure`,
which is the readability obligation the width token exists to carry.

**Visual acceptance criteria**

- [ ] A `dense` panel and a `prose` panel in one frame show **visibly different** distances from
      their border to their first line of text, and the prose panel's line length is visibly shorter
      than the page's full column at 1280.
- [ ] Every panel in every story has a visible boundary against the page in **both** themes: the
      fill change plus the hairline is perceptible without squinting at 100% zoom.
- [ ] No panel story draws a shadow.
- [ ] The nested-panel story shows two distinguishable surfaces, and no story shows three.
- [ ] The loading story's frame is the same size and position as the loaded story's frame — overlay
      the two and the borders coincide.
- [ ] The empty story shows the frame with an `EmptyState` inside it; the no-children story shows
      nothing at all where the panel would be.
- [ ] In the interactive-card composition, the hover capture shows the fill change on the row-link
      area only, and the panel's own border does not change.
- [ ] Corner radius is identical across every panel in the frame, and identical to every other panel
      in the system — a panel that looks softer or sharper than its neighbour fails (FR-013).

---

## 8. `Text`

**Purpose** — put every piece of text in the system on a named typographic role, so that a font
change moves a decision rather than breaking an alignment.

**Anatomy** — one element carrying one role. No wrapper, no icon slot, no decoration. `Text` renders
what it is given and nothing else.

**Variants and sizes** — the six roles from `font.json`'s `role` group, each with a default element
and a default size step. The `as` prop overrides the element within the sanctioned set below and
never outside it, so the role-to-element mapping stays a system decision (FR-020).

| `role`       | Default element | Default size | Weight     | For                                                       |
| ------------ | --------------- | ------------ | ---------- | --------------------------------------------------------- |
| `display`    | `h2`            | `text-2xl`   | `semibold` | headings; the level comes from `Page`/`Section`, not here |
| `body`       | `p`             | `text-md`    | `normal`   | prose, cell text, control labels                          |
| `supporting` | `p`             | `text-sm`    | `normal`   | captions, footnotes, metadata                             |
| `numeric`    | `span`          | `text-md`    | `normal`   | a measured number a reader compares                       |
| `machine`    | `span`          | `text-sm`    | `normal`   | a filename, an error class, a raw string                  |
| `identifier` | `span`          | `text-sm`    | `normal`   | a value the product could not resolve to a name           |

`supporting` is one size step below `body` by `font.json`'s own rule; the role does not bake the size
in, so the pairing is stated here once rather than guessed per call site. `numeric` carries
`tabular-nums` from the token, which is what makes column alignment a decision rather than a
coincidence (SC-009). `identifier` carries `text-secondary` from the token, which is what keeps an
unresolved value visibly distinct from a measured one even for a caller who never read this file.

**A caller never writes a font utility** — no `font-*`, no `text-<size>` outside these roles, no
`leading-*`, no `tracking-*`. That is the whole reason this primitive exists.

**States**

- **default** — as tabled, in `text-primary`, except `identifier`, which is `text-secondary` by
  contract.
- **hover / active** — none. Text is not a control. Text that responds to a pointer is a `Link` (§9)
  or sits inside a `Button`.
- **focus-visible** — none of its own. `Text` is not focusable; a heading that receives programmatic
  focus (a `Callout`'s heading, a route-change announcement) takes `tabIndex={-1}` from its caller
  and shows the standard ring against the surface it sits on.
- **disabled** — `Text` never paints `text-disabled`. Disabled ink belongs to a disabled control's
  own label; de-emphasised standing text is `text-secondary`, and that distinction is what DS-3's
  refusal turned on.
- **loading** — `Text` renders no placeholder. **No dash, no ellipsis, no zero**: a value that has
  not arrived is a `Skeleton` in the caller's hands, because a rendered `0` that later becomes `922`
  was a false statement for as long as it was on screen (SC-010).
- **error** — none. `Text` never colours itself `danger`. A failure has a component (`Field`'s error
  line, `ErrorState`, `Callout`); text that turns red on its own is a failure with no owner and no
  recovery path.
- **empty** — `Text` with no children renders nothing, not an element occupying a line box. An empty
  paragraph is invisible in a screenshot and visible in the rhythm, which is the worst combination.

**Tokens used** — typography roles `type-display`, `type-body`, `type-supporting`, `type-numeric`,
`type-machine`, `type-identifier`; sizes `text-xs` … `text-3xl`; weights `normal` / `semibold`;
`tracking-tight` on `display` at `text-2xl` and above only. Colour `text-primary`, `text-secondary`
(and `text-secondary` by contract on `identifier`). No fill, no border, no radius, no elevation, no
motion.

**Spacing** — none. `Text` carries no margin in any direction; the distance to its neighbours belongs
to `Section`, `Panel` or the density class. A primitive that shipped its own bottom margin would put
a fourth spacing authority in the system.

**Responsive** — the roles and their sizes are identical at 375, 768 and 1280. Text wraps; it does
not truncate. There is no line-clamp prop: unintended truncation is an FR-018 failure, and a caller
that genuinely needs to clamp is describing a composite's decision, made in that composite's spec
with the full value reachable another way.

**Accessibility** — the element is real: a heading is a heading, a paragraph is a paragraph, and a
`span` is used only where the text is a phrase inside a line. Contrast is `text-primary` or
`text-secondary` against the four surfaces, all eight pairs already in the README table for both
themes. At 200% zoom every role reflows without clipping, because every size is rem-derived.

**Visual acceptance criteria**

- [ ] A specimen story showing all six roles at once renders six visibly distinguishable treatments —
      and specifically, `numeric`, `machine` and `identifier` are distinguishable from each other,
      which is the split DS-8 existed to make (a story where all three look identical fails).
- [ ] A column of numbers of differing digit counts, rendered with `numeric`, aligns digit-for-digit;
      the column's right edge is a straight line in the screenshot.
- [ ] `identifier` renders in the secondary ink in both themes, visibly quieter than a `numeric`
      value beside it.
- [ ] The loading story shows a skeleton where the value goes — no digit, no zero, no dash.
- [ ] A paragraph at `body` and a caption at `supporting` differ in size in the screenshot; they are
      not distinguished by colour alone.
- [ ] At 375 no role's text is clipped, and no long unbroken string pushes the page wider than the
      viewport.
- [ ] A page composed of `display`, `body` and `supporting` shows three clear levels of hierarchy at
      a glance — a token-correct implementation that used `body` for a heading would fail (FR-063).

---

## 9. `Link`

**Purpose** — take the reader somewhere else, and be recognisable as doing so without the reader
having to hover to find out.

**Anatomy**

```
Link                       a real <a href> — never a div, never a button that navigates
├─ Label                   the text, always present
└─ ExternalMark  optional  a small drawn mark, aria-hidden, plus visually hidden "(opens in a new tab)"
```

**Variants and sizes** — two variants, one closed decision each:

| Variant              | For                                         | Shape                                                              |
| -------------------- | ------------------------------------------- | ------------------------------------------------------------------ |
| `inline` _(default)_ | a link inside running prose                 | inherits the surrounding role and size; permanent underline        |
| `standalone`         | a navigation or action link on its own line | `type-body`, `text-md`; permanent underline; 44px minimum hit area |

`external` is not a third variant — it is a property of a link whose `href` leaves the product, and
it adds the mark and the hidden text to either variant. A variant that exists to accommodate one call
site is rejected by FR-031, and "external" is a fact about the destination, not a different kind of
link.

**States**

- **default** — ink `link`, underline present at `border.hairline` thickness. The underline is
  permanent and non-negotiable: a link is never distinguished by colour alone (FR-006, README rule
  4).
- **hover** — ink `link-hover`, underline thickens to `border.ring`. Two signals, one of which is not
  colour, so the two frames are distinguishable in a still image and by a reader who cannot separate
  the two inks (FR-037). Transition `motion.duration.fast`, `ease-standard`, colour only — the
  thickness switches instantly, because an animating underline is motion carrying a state change.
- **focus-visible** — `outline-ring` at `outline-offset-ring` in `focus-ring`, around the whole link
  box, on top of whatever the hover paint is. Never removed on pointer interaction (FR-050).
- **active** — `standalone`: the hover paint plus a `surface-sunken` fill behind the link's box, the
  same press feedback every other control in the system gives (FR-038). `inline`: the hover paint,
  with **no** fill — painting a wash behind three words inside a paragraph breaks the line and the
  press is a frame the reader never sees. The difference is stated rather than smoothed over,
  because FR-038 permits a difference a spec states and forbids one it does not.
- **disabled** — **a link is never disabled.** A destination the reader may not reach renders as
  `Text` with a sentence saying why. A greyed-out anchor is a promise with no way to collect on it,
  and it is still in the tab order in half the implementations that ship it.
- **loading** — none. Navigation is the browser's, and a link that spins is a link that has become a
  button. Where an action must show progress, the call site uses a `Button`.
- **error** — none of its own. A navigation that fails lands on a route that renders `ErrorState`.
- **empty** — a `Link` with no text renders nothing. **An icon-only link is forbidden** in this tier
  (README's iconography contract): the mark is never the thing that is named.

**Visited** — ink `link-visited`, underline unchanged. It cannot be observed in a real render —
browsers restrict `:visited` and report the unvisited colour — so its criterion is the token-swatch
story README already specifies, not a story of real anchors.

**Tokens used** — colour `link`, `link-hover`, `link-visited`, `focus-ring`, `surface-sunken`
(`standalone` press only). Border widths `border.hairline` (rest underline), `border.ring` (hover
underline), `border.ring` / `border.ring-offset` (focus ring). Typography: inherited for `inline`,
`type-body` at `text-md` for `standalone`. Motion `duration.fast`, `ease-standard`. Elevation `none`.
Contrast: the twelve `link` / `link-hover` / `link-visited` rows in the README table, on all four
surfaces, in both themes — referenced, not restated. Light `link` on `surface-sunken` is the
tightest normal-text pair in the whole system and is the one a `standalone` link's own press state
paints, so it is the pair to watch first when either token moves.

**Spacing** — a `standalone` link's hit area reaches 44px by its own padding (`space-3` block
padding against `text-md`), never by an overlay. Sibling standalone links sit `space-3` apart. An
`inline` link adds no spacing at all: it is a run of text inside a line.

**Responsive** — identical ink and underline at all three widths. `standalone` links stack
vertically at 375 and may sit in a row from `md`. `inline` links wrap with their sentence and the
underline wraps with them; a link broken across two lines keeps an underline on both fragments.

**Accessibility** — a real `<a>` with a real `href`. The accessible name is the visible text and says
where it goes: never "here", never "click here", never a raw identifier where a human-readable name
exists (FR-051). An external link's hidden "(opens in a new tab)" is real text in the reading order,
and the mark beside it is `aria-hidden` — the decorative shape from README's iconography contract,
never an `aria-label` racing the text. Enter activates; the browser owns modifier-clicks, which is
why this is an anchor and not a click handler.

**Visual acceptance criteria**

- [ ] Every link in every story is underlined at rest — greyscale the screenshot and every link is
      still identifiable as a link.
- [ ] The hover capture differs from the rest capture in **two** ways: the ink is different and the
      underline is visibly thicker.
- [ ] The focus capture shows a ring around the whole link box, offset from the text, in both themes,
      and the underline is still present under it.
- [ ] The `standalone` press capture shows a fill behind the link's box; the `inline` press capture
      shows no fill.
- [ ] The external-link story shows the mark after the label, on the same line, never wrapping alone
      onto the next line.
- [ ] A `standalone` link's tappable box measures at least 44px in both axes at 375 — measurable from
      the rendered box, not from the glyph.
- [ ] The token-swatch story paints `link`, `link-hover` and `link-visited` on all four surfaces and
      shows three distinct colours, the last visibly spent rather than merely darker.
- [ ] In a paragraph containing two links, the links are legible as part of the sentence and the
      paragraph still reads as prose — a token-correct implementation that made every link shout
      fails this criterion (FR-063).

---

## 10. `Table`

**Purpose** — let a reader compare rows of measured values by eye, quickly, with the digits lined up
and nothing decorative between them.

**Anatomy**

```
Table
└─ ScrollRegion            the bounded, keyboard-scrollable container (§ overflow)
   └─ <table>
      ├─ <caption>         required; visually hidden when a heading above already names the table
      ├─ <thead>           one row of <th scope="col">
      ├─ <tbody>           rows; each row's identity cell is <th scope="row">
      └─ <tfoot> optional  a totals or summary row
```

**Variants and sizes** — no variants. One prop: `density`, `dense` (default) or `prose`, whose row
padding and body typography are §3's. Column alignment is declared per column as `text` or `numeric`
and nothing else — a two-value vocabulary, because an alignment a caller can invent is an alignment
two tables will disagree about.

**Numeric columns** — right-aligned, rendered through `type-numeric`, header cell right-aligned to
match. Alignment survives a change of the monospace family because the role declares `tabular-nums`
rather than inheriting it (SC-009, DS-8).

**No zebra striping, ever.** Rows are separated by a `border-hairline` rule in `border` — the
treatment `MatchRow` already ships. A striped fill is a texture running behind a column of numbers,
which README rule 1 forbids outright, and it buys nothing a 1px rule does not.

**The header row is quieter than the data.** Column labels are `type-body` at `text-sm`, weight
`normal`, in `text-secondary`. The data is the thing being read; a bold dark header competes with it
for the first fixation. This is deliberate and is not an oversight to "fix" later.

**Overflow — one definition, decided here** (FR-026, T546). When the table is wider than its
container, **the table's own scroll region scrolls horizontally and the page does not**. Concretely:

- The scroll region is bounded by the same `border-hairline` / `rounded-panel` frame a `Panel`
  draws, and the table is clipped at that frame. A column visibly cut at the inline-end edge is the
  overflow cue — no gradient, no fade, no shadow, because any of those is a texture across the
  numbers in the last column.
- The scroll region is focusable (`tabIndex={0}`) and carries `role="region"` with
  `aria-labelledby` pointing at the caption, so a keyboard user can scroll it and knows what they
  are in. This is the standard pattern and the only reason a non-interactive box may take focus.
- **Columns are ordered identity-first**: the `<th scope="row">` identity column is the first
  column, so the column that gets clipped is always the least identifying one.
- A composite that would rather change shape than scroll — `MatchList`'s cards below `xl` — is making
  a structure decision under FR-019, in its own spec, rendering **exactly one** structure at a time.
  That is a composite's right and not this primitive's behaviour; `Table` scrolls.

**States**

- **default** — as above.
- **hover** — a row highlights with `surface-sunken` **only when the whole row is a real link**;
  otherwise no row hover, because a highlight that leads nowhere invites a click that does nothing.
  Column headers never highlight (nothing here sorts today).
- **focus-visible** — the scroll region shows the standard ring when it is focused for scrolling; a
  focusable element inside a cell shows its own ring, offset so the frame does not clip it.
- **active** — a row link's press paints `surface-sunken` with the row's rule retained. The table
  itself has no active state.
- **disabled** — never. A table whose data is stale says so in a `Callout` above it; a greyed table
  is unreadable and still on screen.
- **loading** — caption and header row render immediately; the body holds skeleton rows of the same
  height as real rows, at a caller-supplied count. `aria-busy="true"` sits **once** on the scroll
  region, never per cell — "a skeleton per cell announced per cell is a screen reader reading the
  word 'loading' forty times for one table" (FR-054, T532). No cell renders a `0` or a `—` while
  loading.
- **error** — caption and header row are retained; the body is one cell spanning every column,
  containing one `ErrorState` with a retry. Keeping the header tells the reader what failed to
  arrive.
- **empty** — caption and header row are retained; the body is one cell spanning every column,
  containing one `EmptyState` with its sentence. A table that renders its header over nothing, with
  no words, is the defect FR-023 names.

**Tokens used** — colour `surface` (the region's fill), `border` (the frame and every row rule),
`text-primary` (data), `text-secondary` (column labels, caption when visible), `surface-sunken` (row
link hover and press), `focus-ring` (the region's ring). Typography `type-numeric`, `type-machine`,
`type-body` per §3 for `dense`; `type-body` / `type-supporting` for `prose`. Radius `rounded-panel`
on the region. Border widths `border.hairline`, `border.ring`, `border.ring-offset`. Elevation
`none`. Motion `duration.fast` / `ease-standard` for a row link's hover fill; nothing else moves.

**Spacing** — cell block padding `space-3` at `dense`, `space-4` at `prose` (§3). Cell inline
padding `space-4` between columns, `space-4` from the frame on both edges. An icon-and-text pairing
inside one cell sits at `space-2` (within a component). Two stacked lines inside one cell sit at
`space-1`, the tight step the `dense` class names.

**Responsive** — the table's structure is identical at 375, 768 and 1280; only the scroll region's
available width changes. At 375 a wide table is scrollable inside its frame and **the page is not**.
Cell padding does not shrink at narrow widths: a data tool that squeezes its rows to avoid a scroll
has traded legibility for tidiness, and the trade goes the other way here.

**Accessibility** — a real `<table>` with a real `<caption>`, `<th scope="col">` on every column
header and `<th scope="row">` on every row's identity cell (FR-026). No `role="table"` on a `div`.
The scroll region is a labelled, focusable region. Row links are real anchors covering the row, so
modifier-clicks work. Contrast: `text-primary` and `text-secondary` on `surface` and on
`surface-sunken` (the hovered row), all four pairs already in the README table for both themes.

**Visual acceptance criteria**

- [ ] In a table of numbers with differing digit counts, the digits align in a straight vertical line
      and every numeric column is right-aligned, header included.
- [ ] No row has a background fill different from its neighbour at rest — no zebra striping in any
      story, in either theme.
- [ ] Row separators are a single hairline rule, identical between every pair of rows.
- [ ] The column header row is visibly quieter than the data rows — a token-correct implementation
      with a bold, dark header that out-shouts the numbers fails this criterion (FR-063).
- [ ] At 375, the overflow story shows a column clipped at the frame's inline-end edge, the frame
      itself fully inside the page padding, and **no horizontal scrollbar on the page**.
- [ ] The overflow story shows no gradient, fade or shadow over the clipped column.
- [ ] The loading story shows the caption and header with skeleton rows of the same height as the
      loaded story's rows — overlay the two and the header does not move.
- [ ] The empty and error stories both still show the column headers, with one `EmptyState` or one
      `ErrorState` spanning the body.
- [ ] In the row-link hover capture, exactly one row is filled and the row rules are still visible
      through the fill.
- [ ] A `dense` and a `prose` table in one frame have visibly different row heights.

---

## 11. `Field`

**Purpose** — put a control, its label, its hint and its error together so that they cannot come
apart, and so a reader who cannot see colour still knows which control failed and why.

**Anatomy**

```
Field
├─ Label                   always rendered; <label for> the control
├─ Control                 the slot: input, select, textarea — supplied by the caller
├─ Hint       optional     supporting text, always present when present (never hover-only)
└─ ErrorLine  conditional  the error, in words, rendered only when there is one
```

**Variants and sizes** — no variants. Two sizes, matched to `Button`'s so a field and its submit
button sit on one line at the same height (FR-038): `md` — control height `space-10`, pointer-only;
`lg` — control height `space-12` (48px, clearing 44px), used at every width where touch is expected.
A field reachable on a touch viewport renders at `lg`.

`labelHidden` renders the label visually hidden and is permitted only where an adjacent visible
element already names the control — the search field beside a visible "Search" button is the shipping
case. It is not a way to make a form look cleaner.

**States**

- **default** — label `text-primary` at `type-body` / `text-sm`, weight `semibold`; control fill
  `surface` with a `border-hairline` in `border-strong` (the non-text 3:1 pair the README table
  carries for every surface a control sits on); hint `type-supporting` at `text-sm` in
  `text-secondary`; `rounded-control`.
- **hover** — the control's boundary deepens to `border-strong` on a `surface-sunken` fill; the label
  and hint do not change. Nothing moves and nothing grows.
- **focus-visible** — `outline-ring` at `outline-offset-ring` in `focus-ring` around the control,
  never around the whole field. The label is not a focus target.
- **active** — the control's own text-entry state; no separate paint. A press on a text input is
  indistinguishable from focusing it, and pretending otherwise would be inventing a state.
- **disabled** — control fill `surface-sunken`, boundary `border`, ink `text-disabled`, label
  `text-disabled`, hint retained in `text-secondary`. **A disabled field carries a visible sentence
  saying why**, exactly as a disabled `Button` does. The hint is never the thing that disappears when
  the control does.
- **loading** — the control is disabled with `aria-busy="true"` on the field, the label and hint stay
  at full contrast, and no skeleton replaces the label. A form that dissolves into grey blocks while
  submitting has lost the reader's place in it.
- **error** — control boundary `danger` at `border.hairline`, and the `ErrorLine` renders beneath the
  control in `danger` at `text-sm`, prefixed by the field's own name so it reads as a sentence
  ("Profile id — enter digits only"). The control carries `aria-invalid="true"` and
  `aria-describedby` pointing at both hint and error. **The colour is never the only signal**: the
  words are, and they are always there. An error appearing **after** the initial render carries
  `role="alert"` on the error node so it is announced (FR-053); an error present at first paint does
  not, because that double-announces.
- **empty** — an empty **value** is not an error. A required field that has never been touched shows
  its default paint; it errors on blur or on submit, never on first render. The control renders no
  placeholder text standing in for a label (a placeholder disappears the moment the reader types,
  which is the moment they need it).

**Tokens used** — colour `surface`, `surface-sunken`, `border`, `border-strong`, `danger`,
`text-primary`, `text-secondary`, `text-disabled`, `focus-ring`. Radius `rounded-control` — the role
shared with every button and input, so two controls of the same role cannot differ. Border widths
`border.hairline`, `border.ring`, `border.ring-offset`. Typography `type-body` (label, control text),
`type-supporting` (hint, error). Motion `duration.fast`, `ease-standard` on the boundary colour only.
Elevation `none`. Contrast: `danger` on `surface` and on `surface-raised`, and `border-strong` on
each of the four surfaces, are all in the README table for both themes.

**Spacing**

| Between          | Step      |
| ---------------- | --------- |
| Label to control | `space-2` |
| Control to hint  | `space-2` |
| Control to error | `space-2` |
| Field to field   | `space-4` |

Fields sit `space-4` apart rather than at the `space-6` between-components step: a form is one
component, and its fields are its internals.

**Responsive** — 375: `lg` size, label above the control, control full width. 768 and 1280: label
stays above the control (a side-by-side label makes the error's position ambiguous), control width
bounded by its column. The hint and the error never move to a tooltip at any width — a fact revealed
only on hover is unreachable by touch (FR-039).

**Accessibility** — a real `<label for>` bound to a real control; the association is never made by
proximity and never by `aria-label` where a visible label exists. `aria-describedby` carries the hint
and, when present, the error. `aria-invalid` marks the control, not the field. The error is text
first and colour second (FR-025). Touch target ≥ 44px at `lg`, reached by the control's own height.
Tab order is label-less: control, then the next field's control.

**Visual acceptance criteria**

- [ ] Every field in every story shows a visible label above its control — no story relies on a
      placeholder to name a control.
- [ ] The error story shows a coloured control boundary **and** a sentence beneath it; converting the
      screenshot to greyscale leaves the error still identifiable.
- [ ] The error sentence names the field, so it reads as a complete statement on its own.
- [ ] The disabled story shows the greyed control **and** a visible sentence explaining why.
- [ ] The focus capture shows a ring around the control only, offset from its boundary, in both
      themes.
- [ ] At 375 the control's box measures at least 44px tall.
- [ ] In a form of three fields, the distance between two fields is visibly smaller than the distance
      from the form to the next component — a token-correct implementation that spaced its fields as
      far apart as its sections would fail (FR-063).
- [ ] The hint is present in the resting screenshot, not only on hover or focus.

---

## 12. `EmptyState`

**Purpose** — say why a region has nothing in it, and offer the action that would fill it, so a
reader never has to decide whether the product is broken or simply has no data for them.

**Anatomy**

```
EmptyState
├─ Heading                 what is not here, in six words or fewer
├─ Explanation             why, in one or two sentences, in the reader's terms
└─ Action      optional    the one thing that would fill the region
```

**No illustration and no icon.** A drawing here would either be an Age of Empires II asset (a licence
question this tier does not need to open, README rule 3) or generic decoration that costs vertical
space in a tool people consult quickly (README rule 1). The words are the state.

**Variants and sizes** — no variants, one size. It is as tall as its text; there is **no minimum
height**, because a reserved empty box is the thing this component exists to replace. It renders no
surface of its own: a caller that wants a bounded region wraps it in a `Panel`, and inside a `Table`
it sits in a body cell spanning every column (§10).

**States**

- **default** — heading `type-display` at `text-xl` in `text-primary`; explanation `type-body` at
  `text-md` in `text-secondary`; optional `Button`, `secondary` variant, because an empty region is
  rarely the page's single recommended action.
- **hover / focus-visible / active** — none of its own; the action inside it carries `Button`'s.
- **disabled** — never. An empty state that cannot be acted on is an empty state with no action prop,
  not a greyed-out one.
- **loading** — not applicable, and the distinction is load-bearing: while a region is loading it
  shows `Skeleton`s, and `EmptyState` renders only once the request has **settled** with nothing in
  it. An `EmptyState` that flashes before data arrives has told the reader something false.
- **error** — not applicable. A region that failed renders `ErrorState` (§13), never "no results".
  "Nothing here" and "we could not find out" are different facts and a reader acts differently on
  each; conflating them is the most common form of this defect.
- **empty** — an `EmptyState` with no heading and no explanation renders **nothing at all**. There is
  no such thing as an empty empty state, and a wordless one is the blank region FR-023 forbids.

**Tokens used** — colour `text-primary` (heading), `text-secondary` (explanation). Typography
`type-display` at `text-xl`, `type-body` at `text-md`. No fill, no border, no radius, no elevation,
no motion. It inherits the surface class of whatever contains it.

**Spacing** — heading to explanation `space-2`; explanation to action `space-4`; block padding
`space-8` above and below when it stands alone inside a `Panel` or a `Section` body, so the region
reads as deliberately empty rather than as a rendering accident. Text is bounded to `max-w-measure`
so the explanation is one readable paragraph, not one wide line.

**Responsive** — identical at all three widths; text left-aligned at every one. Not centred: a
centred block in a left-aligned data tool reads as a different page rather than as an empty region
of this one, and centring makes the explanation harder to scan.

**Accessibility** — the heading is a real heading at the level the surrounding `Section` or `Panel`
implies, never a styled `div`. The explanation is real text in the reading order. The action, when
present, is a real `Button` or `Link` with a name that says what it does. Nothing is announced by
`aria-live`: an empty state present at first paint that announces itself is noise.

**Visual acceptance criteria**

- [ ] Every empty story contains at least one full sentence — no story shows an icon, a dash or a
      bare "No data".
- [ ] No empty story renders an illustration, an icon or a decorative mark of any kind.
- [ ] The empty state is left-aligned, and its paragraph is visibly narrower than a full 1280px
      column.
- [ ] An `EmptyState` and a `Skeleton` of the same region, captured side by side, are unmistakably
      different — one is words, the other has no text at all (SC-010's distinction, in a picture).
- [ ] Where an action exists it is a real button, and it is the only button in the region.
- [ ] The no-content story renders nothing at all, not a padded blank box.
- [ ] Inside a `Table`, the empty state sits under the retained column headers and spans the full
      table width.

---

## 13. `ErrorState`

**Purpose** — tell a reader what failed, in their terms, and give them the way forward, so a failure
is a detour rather than a dead end.

**Anatomy**

```
ErrorState
├─ ToneStripe              a 2px inline-start rule in `danger` — a rule, not an icon
├─ Heading                 what failed, in the reader's terms
├─ Explanation             what it means for them, and what happens next
├─ Action                  the recovery: retry, go back, or a contact route
└─ TechnicalDetail  optional  an error code or reference, in `type-machine`, for a support message
```

The stripe-and-heading grammar is `Callout`'s, deliberately: a reader who has learned one failure
grammar in this product should not have to learn a second. What differs is scope — `Callout` sits
beside content that is still there, `ErrorState` replaces content that is gone (§1).

**Variants and sizes** — no variants. Tone is always `danger`; an error state in another tone would
be a `Callout`. Size is intrinsic. It renders no surface of its own and takes the surface of whatever
contains it: a `Section` body, a `Panel` body, or a `Table`'s body cell (§10).

**The recovery action is mandatory.** `ErrorState` requires either an action or an explicit
`recovery="none"` with a sentence saying what the reader can do instead ("this match's replay is past
Microsoft's retention window; nothing can retrieve it"). There is no third case, because "a failure
must not leave the control that caused it permanently unusable" (FR-024) is unenforceable if the
absence of an action is silent.

**States**

- **default** — stripe `danger`; heading `type-display` at `text-xl` in `danger`; explanation
  `type-body` at `text-md` in `text-primary` — **body text is always `text-primary`**, the same rule
  `Callout` carries and for the same reason: the tone colours the stripe and the heading only, never
  the paragraph a reader has to read; technical detail `type-machine` at `text-sm` in
  `text-secondary`; action a `Button`, `secondary` variant.
- **hover / focus-visible / active** — none of its own; the recovery action carries `Button`'s.
- **disabled** — never, and this is the state FR-024 is about: the control that caused the failure
  returns to being pressable, and the retry inside an `ErrorState` is never disabled after a failed
  attempt. A retry that greys itself out after failing is how a recoverable error becomes permanent.
- **loading** — a retry in progress shows `Button`'s own loading state (spinner, unchanged width, an
  action-specific label). The `ErrorState` itself does not become a skeleton — the explanation must
  stay readable while the retry runs, or the reader loses the only account of what went wrong.
- **error** — this component **is** the error state. A retry that fails again re-renders it with the
  same anatomy and, where the failure has changed, updated words; it never stacks a second error
  presentation beneath the first.
- **empty** — an `ErrorState` with no heading renders **nothing**, and that is a caller defect a
  story must show: a failure with no words is worse than a blank region, because the region at least
  does not claim to be an explanation.

**Tokens used** — colour `danger` (stripe and heading), `text-primary` (explanation),
`text-secondary` (technical detail). Typography `type-display` at `text-xl`, `type-body` at
`text-md`, `type-machine` at `text-sm`. Border width `border.ring` for the 2px stripe. No fill of its
own, no radius, no elevation, no motion. Contrast: `danger` on `surface`, `surface-raised`,
`surface-sunken` and `background` are all in the README table for both themes — which of the four
applies is decided by the surface the container paints, per the pairing convention.

**Spacing** — stripe to text `space-4`; heading to explanation `space-2`; explanation to action
`space-4`; action to technical detail `space-4`. Block padding `space-6` when it stands alone inside
a `Panel` or a `Section` body. Text bounded to `max-w-measure`.

**Responsive** — identical at all three widths; the stripe stays on the inline-start edge at every
one. The action is full width below `md` and intrinsic from `md`, matching `Button`'s own responsive
rule (FR-038). The technical detail wraps rather than truncating: a half-copied error code is worse
than a long one.

**Accessibility** — `role="alert"` when the error **replaces content after an interaction**, so it is
announced; a plain region with a real heading when it is the initial render of a failed route,
because an alert on first paint double-announces (`Callout`'s rule, same reasoning). The heading is a
real heading at the level its container implies. The recovery action is a real `Button` or `Link`
whose name says what it does ("Try again", never "OK"). The technical detail is selectable text, not
an image and not a tooltip: a reader who must paste it into a support message has to be able to
copy it.

**Visual acceptance criteria**

- [ ] Every error story shows a heading, at least one full sentence of explanation, and either a
      visible action or a sentence stating there is nothing to do.
- [ ] The explanation is in `text-primary`, not in the danger ink, in both themes — a token-correct
      implementation that painted the whole block red fails this criterion (FR-063).
- [ ] The tone stripe is on the inline-start edge and is a rule, not an icon; no story substitutes an
      icon for the heading.
- [ ] No error story shows a raw stack trace, a JSON body or an HTTP status as its heading.
- [ ] The retry-failed story shows the retry button **enabled**, not greyed out.
- [ ] The retry-in-progress story shows the button's spinner with the explanation still fully
      readable above it.
- [ ] Captured beside an `EmptyState` of the same region, the two are unmistakably different: one has
      a stripe and a recovery, the other has neither.
- [ ] At 375 the action is full width and the technical detail wraps without being cut off.
- [ ] Inside a route, the `ErrorState` sits under a retained page title and no failed section's
      content remains beneath it.

---

## 14. Cross-primitive acceptance criteria

These are the criteria that no single primitive can be judged against, and they are the ones SC-004
turns on. `visual-reviewer` applies them to the composition stories (T549's throwaway route, and the
realistic compositions FR-043 requires).

- [ ] **The rhythm test.** In one full-page screenshot containing two sections, three distances are
      measurably different and in this order, smallest to largest: within a component (`space-2`) <
      between components (`space-6`) < between sections (`space-8`). A screenshot where two of the
      three are equal fails, whatever the class names say.
- [ ] **The two-routes test.** A page built from the nine primitives and an existing retrofitted
      route, captured at the same width, have the same content edges, the same page padding and the
      same section rhythm — with no adjustment made to either (SC-004).
- [ ] **The hierarchy test.** In one full-page screenshot the reader can rank, by size and weight
      alone, the page title, a section heading, a panel heading and body text — four levels, in that
      order, with no two adjacent levels ambiguous (FR-063).
- [ ] **The landmark test.** Exactly one `<main>` and exactly one `<h1>` per rendered route. Counted
      by `tests/visual/app-routes.spec.ts`, not read from an image — this is the defect that survived
      279 baselines precisely because it is invisible in one.
- [ ] **The no-overflow test.** At 375, 768 and 1280, no page screenshot has a horizontal scrollbar
      and no content is clipped by the viewport. A wide table scrolls inside its own frame.
- [ ] **The both-themes test.** Every criterion above holds in light and in dark. Judge light first —
      its margins remain the narrower of the two — but a criterion met in one theme and not the other
      is a failure, not a finding.
- [ ] **The greyscale test.** Converted to greyscale, a full-page screenshot still distinguishes a
      link from body text, an error from an empty region, and a numeric column from a text column.
      Nothing in this tier rides on colour alone.

---

## 15. What this file does not decide

- **Which route uses which `Page` width.** That is each route's own decision, recorded in the route's
  container when it is retrofitted (T554, T555). This file fixes the vocabulary of three; it does not
  assign them.
- **Whether a composite changes structure across a width.** `MatchList`'s cards-below-`xl` is a
  composite's decision under FR-019, made in `match-history.md`. `Table` scrolls; it does not
  reshape, and a composite that reshapes renders exactly one structure at a time.
- **The prop names.** FR-032's prop-vocabulary reconciliation is T557's, and it lands with every
  consumer it breaks in one change. Where this file names a prop (`density`, `width`, `role`,
  `align`, `recovery`), it is naming the **concept** the primitive must expose; if T557 renames one,
  the rename lands here too rather than leaving two vocabularies alive.
- **Selection and expansion.** T569 extends the closed vocabulary to ten. None of the nine implements
  either today (§0); when the vocabulary grows, this file gains nine answers, not nine features
  (FR-036: a state is never implemented because the vocabulary lists it).
- **The index row.** `README.md`'s spec index needs a row for this file. T540 already rewrites all 24
  rows of that table's "Component directory" column for the tier move, so the row is added there
  rather than in two separate edits to the same table.
