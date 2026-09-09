# Shared primitives

The three screen specs in this directory (`sign-in-screen`, `archival-control`, `profile-summary`) all
lean on the same small set of components. They are specified once here so the three screens agree and
so no implementer has to invent a resting colour at eleven at night.

Each primitive below carries the nine sections in compressed form. Where a primitive grows a variant
a later feature needs, it earns its own file and this section becomes a stub pointing at it.

Read [`README.md`](./README.md) first: the contrast table and the token gap register are shared, and
nothing below restates them.

**This file specifies seven components, not six** — `Dialog` (§ below) has lived here since feature
001 (`dbc094c`, "extract a shared Dialog primitive from the two dialogs duplicating it") and
`README.md`'s index row for this file omitted it; that row is corrected as part of this amendment
(T570). A tier is a property of a component, and a file naming seven of them declares seven, not one
line for the file:

| Component   | Tier                                    | Surface class                                                                                                                        |
| ----------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `Button`    | primitive (`src/primitives/Button/`)    | neither `dense` nor `prose` — a control draws inside whatever `Panel`, `Table` or `Field` contains it; it owns no surface of its own |
| `Callout`   | primitive (`src/primitives/Callout/`)   | neither `dense` nor `prose` — same reason                                                                                            |
| `Badge`     | primitive (`src/primitives/Badge/`)     | neither `dense` nor `prose` — same reason                                                                                            |
| `Skeleton`  | primitive (`src/primitives/Skeleton/`)  | neither `dense` nor `prose` — same reason                                                                                            |
| `Menu`      | primitive (`src/primitives/Menu/`)      | neither `dense` nor `prose` — its popover is `overlay`-elevated chrome, not a content surface (README's "Surface density" section)   |
| `Dialog`    | primitive (`src/primitives/Dialog/`)    | neither `dense` nor `prose` — same reason, at `modal`                                                                                |
| `StatValue` | primitive (`src/primitives/StatValue/`) | neither `dense` nor `prose` — same reason                                                                                            |

---

## Button

**Purpose** — commit the user to an action, with the visual weight matching how consequential and
how recommended that action is.

**Anatomy** — root `<button>` (or `<a>` when it navigates) / optional leading icon slot / label /
optional trailing icon slot / loading indicator that replaces the leading icon slot without changing
the button's width.

**Variants**

| Variant       | Use                                                              | Resting fill | Resting label     | Resting boundary |
| ------------- | ---------------------------------------------------------------- | ------------ | ----------------- | ---------------- |
| `primary`     | the single recommended action of a view                          | `accent`     | `accent-contrast` | none             |
| `secondary`   | a real alternative, equal in legitimacy, lower in recommendation | `surface`    | `text-primary`    | `border-strong`  |
| `ghost`       | tertiary, in-menu and in-toolbar actions                         | transparent  | `text-primary`    | none             |
| `destructive` | unlink, withdraw consent, erase                                  | `surface`    | `danger`          | `danger`         |

At most one `primary` per view. Two primaries mean the view has not decided what it is for.

`primary` rests on `accent` in **both** themes and darkens through `accent-hover` and
`accent-active`. The three are deliberately three distinct colours: a control whose hover looks
identical to its rest has not told the user it responded.

`destructive` deliberately does not fill with `danger`: there is no `danger-hover` or
`danger-active` token, and inventing one is forbidden. Its hover deepens by swapping the fill to
`surface-sunken` and keeping `danger` for label and boundary.

`secondary`, `ghost` and `destructive` step through the surface ramp's two attenuated rungs, one
per state, rather than the one rung repeated at both (remediation, FR-037: two states of a control
must be distinguishable in a still image, not merely painted with the same class twice). **Hover
deepens to `surface-sunken`**, the ramp's darkest surface and always darker than whatever the button
sits on. **Active moves to `background`**, the ramp's other attenuated step — a different token from
hover's, already measured in the README contrast table (`text-primary` / `danger` on `background`
and on `surface-sunken` are both asserted rows) — so a screenshot of the two states is never
byte-identical. `background` cannot serve as the _hover_ fill instead: several `ghost` buttons render
directly on a `bg-background` page (`Page`'s `actions` slot — `DashboardContainer`'s "Search
players" / "Sign out") and `ghost` carries no boundary until `active`, so a `background`-filled hover
would be invisible there; `surface-sunken` never is, because nothing it can sit on is darker than it.
`ghost` also gains its `border-strong` boundary only at `active`, never `hover`, so pressing adds a
shape signal — a border appearing — on top of the fill change; `secondary` carries `border-strong` at
every state (it is part of its resting anatomy, so repeating it at `active` was a dead declaration
and is removed); `destructive` carries `border-danger` at every state instead of swapping to the
neutral `border-strong` on press, so a pressed destructive button never reads as merely neutral.

**`destructive` is not a second spelling of `danger` (FR-032, T557, README's rule 9).** The two look
like the same word for the same idea, and they are not: `destructive` names what this button _does_
— commits an irreversible action — the same axis `primary`/`secondary`/`ghost` sit on, while `danger`
names what a _message_ means, the axis `Callout`'s and `Badge`'s tone scale carries. The table above
already shows the layering rather than a collision: `destructive` paints its label and boundary with
the `danger` token because a consequential action and a dangerous message share a colour, not a
name. Renaming `destructive` to `danger` would put a message-severity word on an action-hierarchy
scale next to `primary` and `secondary`, which is the inconsistency, not the fix.

**Sizes** — `md`: height `space-10`, padding-inline `space-4`, font-size `sm`. `lg`: height
`space-12`, padding-inline `space-6`, font-size `md`. **`md` is pointer-only.** Any button reachable
on a touch viewport renders at `lg` (48px, clearing the 44px minimum), or `md` with the hit area
extended to 44px by padding rather than by a transparent overlay.

**States**

- **default** — as tabled above.
- **hover** — `primary`: fill `accent-hover`, in both themes. `secondary` / `ghost` /
  `destructive`: fill `surface-sunken`. Transition `motion.duration.fast` with `easing.standard`;
  colour only, no lift, no scale.
- **focus-visible** — `outline-2 outline-offset-2` in `focus-ring` (gap DS-4), on top of whatever
  the hover state is. Never removed on mouse click; never replaced by a fill change alone.
- **active** — `primary`: `accent-active`. `secondary` / `ghost` / `destructive`: fill `background`
  — a different token from `hover`'s `surface-sunken`, so pressing repaints rather than repeating
  the hover frame. `ghost` additionally gains a `border-strong` boundary it does not carry at
  `hover`; `secondary` keeps the `border-strong` boundary it already carries at rest; `destructive`
  keeps `border-danger`, never swapping to a neutral boundary. No translate, no shadow change.
- **disabled** — fill `surface-sunken`, label `text-disabled`, boundary `border`, cursor default,
  `disabled` attribute set. A disabled button must be accompanied by visible text saying why, in
  `text-secondary`; a button that is grey with no explanation is a dead end.
- **loading** — `aria-busy="true"`, `disabled`, label replaced by an action-specific present
  participle supplied by the caller ("Taking you to Steam…"), spinner in the leading slot. Width
  does not change: reserve the icon slot at rest. A caller that gives no loading label gets the
  original label plus the spinner, never a bare spinner.
- **error** — the button has no error state of its own. The failure renders in a `Callout` beside or
  above it and the button returns to `default` and to being pressable. A button that stays disabled
  after a failure is the most common way a retry becomes unreachable.
- **empty** — not applicable: a button with no label is invalid. An icon-only button carries
  `aria-label` and is forbidden on the primary path of every screen in this feature.
- **selection** — not applicable. A `Button` is an action, not a set member; a control that marks
  one of several choices as current is `Menu`'s `selection` variant (below), never a row of buttons
  standing in for it.
- **expansion** — not applicable to `Button` itself. A button that opens a popover (`Menu`'s
  trigger) or a modal (`Dialog`'s opener) carries `aria-expanded`/`aria-haspopup`, but that attribute
  is part of the _trigger contract_ those components define, not a state `Button` owns on its own
  (FR-036 — a state is documented where it is real, not built into every component the vocabulary
  could apply to).

**Tokens** — colour `accent`, `accent-hover`, `accent-active`, `accent-contrast`, `surface`,
`background`, `surface-sunken`, `border`, `border-strong`, `text-primary`, `text-secondary`,
`text-disabled`, `danger`, `focus-ring`. Radius `md`. Font family `sans`, size `sm` / `md`, weight
`semibold`. Motion `duration.fast`, `easing.standard`. Elevation `none` — buttons do not float.

**Spacing** — icon-to-label `space-2`. Sibling buttons `space-3` apart.

**Responsive** — below `md`, a button that is the sole action of its block is full-width; siblings
stack vertically at `space-3`, recommended action first. From `md` up, buttons are intrinsic width
and sit on one row.

**Accessibility** — real `<button type="button">`, or `<a>` when it navigates (never a `<div>` with
a click handler). Space and Enter activate. Touch target ≥ 44px. Label contrast per the README
table; `accent-contrast` on `accent` in the light theme is the tightest pair `primary` depends on
and must be verified, not assumed.

**Acceptance** — exactly one `primary` per screenshot — a token-correct screen that painted two
controls `accent` still fails this criterion, because the reader cannot tell which action the view
recommends (FR-063); focus ring visible and 2px offset from the edge on the keyboard-focused button;
the default, hover and active screenshots are three distinguishable frames for **every** variant —
`primary`'s hover fill is visibly darker than its resting fill and its active fill darker again;
`secondary` / `ghost` / `destructive`'s hover fill (`surface-sunken`) and active fill (`background`)
are two different, already-measured tokens, and `ghost`'s active additionally draws a boundary its
hover does not — loading button shows a spinner and the same width as at rest; disabled button has
visible explanatory text near it.

---

## Callout

**Purpose** — explain an outcome the user did not ask for, and offer the way forward, in place
rather than in a toast that disappears.

**Anatomy** — root region / tone stripe (a 2px inline-start rule, not an icon) / heading / body
paragraphs / action row / optional dismiss control.

**Variants** — `info`, `success`, `warning`, `danger`. Tone drives the stripe colour and the heading
colour only. **Body text is always `text-primary`.** In the light theme `warning` sits below the
normal-text floor by design (README table) — it owes only the large-text and non-text floor, because
it never colours anything but a stripe and a heading — and the rule "body is always `text-primary`"
is what keeps that from becoming a per-component judgement call.

Tone is a claim about the world, not about volume:

- `info` — this is an explanation. Nothing went wrong. Use it for anything the user's own history
  caused, `no_aoe2_profile` and `not_allowlisted` above all.
- `warning` — something will go wrong if nothing changes.
- `danger` — something failed, or is about to be irreversible.
- `success` — a state has been reached and is worth confirming.

**Sizes** — one. Padding `space-4` below `md`, `space-5` from `md` up.

**States** — **default** as above. **hover / active** — none; the root is not interactive. Actions
inside it have their own. **focus-visible** — when the callout receives programmatic focus (see
sign-in-screen), the heading takes `tabindex="-1"` and paints no ring of its own — corrected by
remediation, B5 (fourth-pass adversarial review); this used to say "shows the standard focus ring,"
which was never true (Chromium's user-agent default outline painted instead, in no token file) and
is the wrong target regardless: a `tabindex="-1"` heading is never reached by a reader's own Tab
press, only by a caller's one-off `.focus()` call (`sign-in-screen.md` §8) to draw assistive
technology's attention to an outcome that just appeared — the same shape and the same reasoning as
`Dialog`'s heading below, "its focus is for the accessible-name announcement, not a visible
indicator." `outline-none` on the heading is what makes that true rather than aspirational.
**disabled** — none; a callout is never disabled. **loading** — none; a callout describes a settled
outcome. Anything still resolving is a `Skeleton`. **error** — `danger` is that state.
**empty** — a callout with no heading and no body renders **nothing at all**, not an empty bordered
box. This is the state that ships by accident, so the acceptance criteria test for it.
**selection** — not applicable; a callout is not a set member. **expansion** — not applicable; the
optional dismiss control removes the callout, it does not reveal a second surface, which is a
different shape from `Menu`'s trigger (below).

**Tokens** — colour `surface-raised` (fill), `info` / `success` / `warning` / `danger` (stripe and
heading), `text-primary` (body), `text-secondary` (any timestamp or footnote), `border`. Radius
`lg`. Font size `md` heading / `sm` body, weight `semibold` heading / `normal` body. Elevation
`none` — it sits in the page, it does not hover over it.

**Spacing** — heading to body `space-2`; between body paragraphs `space-3`; body to action row
`space-4`.

**Responsive** — full width of its column at every viewport. Actions stack below `md`.

**Accessibility** — `role="status"` for `info` / `success` / `warning`, `role="alert"` for `danger`.
`aria-labelledby` pointing at the heading. Body ≤ 75 characters per line (gap DS-6). Never
`aria-live` on a callout that is present at first paint — that double-announces.

**Acceptance** — tone stripe visible on the inline-start edge; body text is the primary text colour
in both themes; no icon substitutes for the heading; an empty callout is absent from the screenshot
rather than present and blank; the heading (`semibold`) is visibly heavier than the body (`normal`)
even though both share a surface — a token-correct callout that gave both the same weight would read
as one undifferentiated paragraph and fails this criterion (FR-063).

---

## Badge

**Purpose** — mark one item in a list as being in a named state, at a glance.

**Anatomy** — root `<span>` / label text. No icon-only form.

**Variants** — `neutral` (fill `surface-sunken`, label `text-secondary`, boundary `border`),
`accent` (fill `surface-raised`, label `accent` in dark / `accent-active` in light — the README table
is why the light theme uses the darker token, and this is the one place `accent` appears as text).

**Sizes** — one: height `space-5`, padding-inline `space-2`, font-size `xs`, weight `semibold`,
tracking `wide`, radius `full`.

**States** — **default** only. **hover / focus-visible / active** — none: a badge is not
interactive and must never be the control that changes the state it names. **disabled / loading** —
none; during a state change the badge is replaced by a `Skeleton` of the same footprint.
**error** — none.
**empty** — a badge with no label renders nothing. **selection** — not applicable to `Badge` on its
own: a selection state's still-image mark is `Menu`'s own intrinsic checkmark glyph
(`shared-primitives.md#Menu`, T572), not `Badge`. A `Badge` beside a checked item (`Menu`'s
`selection` variant, `ProfileSummary`'s profile switcher) is an _additional_ signal carrying a
different, caller-chosen fact (`Current`, `Primary`) — never the selection mark itself, and never
the thing that is itself selected. **expansion** — not applicable; a badge never reveals a second
surface.

**Tokens** — `surface-sunken`, `surface-raised`, `border`, `text-secondary`, `accent`,
`accent-active`. Radius `full`. Font size `xs`, weight `semibold`, tracking `wide`.

**Responsive** — identical at all viewports.

**Accessibility** — the label is real text, read in document order with the item it qualifies. Never
communicated by colour or shape alone.

**Acceptance** — the badge reads as a word at 375px without truncation; it is never the only
difference between two rows in a screenshot; its `semibold` weight and `wide` tracking keep it
legible at `xs` beside `sm` body text in the same row — a token-correct badge that dropped to
`normal` weight would blur into the surrounding text and fails this criterion (FR-063).

**Tone variants (US3, `capture-state-badge.md`)** — `Badge` grows four more variants,
`success` / `warning` / `danger` / `info`, each a `surface-raised` fill with a tone-coloured label
and a transparent boundary, the same shape `accent` already established. Full spec — including why
the fill stays neutral rather than tone-tinted, and the one theme-branching exception `accent`
needed that these four do not — lives in
[`capture-state-badge.md`](./capture-state-badge.md#5-badge-tone-variants-new-added-to-shared-primitivesmds-badge),
which is also where `CaptureStateBadge`, the composite that actually chooses a tone, is specified.

**`Badge`'s prop is `variant`, not `tone`, even though four of its six members are `Callout`'s
entire `tone` scale (FR-032, T557, README's rule 9).** The two are not the same prop under two
names: `Callout`'s `tone` is required and always carries semantic weight — a callout with no
meaning to convey would not exist — while two of `Badge`'s six values, `neutral` and `accent`, carry
none at all. Naming the whole prop `tone` would misdescribe those two. Where the scales genuinely
overlap — `success`/`warning`/`danger`/`info` — they already share the identical four spellings in
both components; that is the part of this that was worth reconciling, and it already was, before
this survey.

---

## Skeleton

**Purpose** — hold the shape of content that is arriving, so nothing jumps when it lands.

**Anatomy** — one or more blocks, each matching the footprint of the element it stands in for.

**Variants** — `text` (height matching a line-height token, width 60–90% varied per line), `number`
(the exact footprint of the numeral it replaces), `block`.

**Sizes** — derived from the content, never chosen freely.

**States** — **loading** is the only real state; the component exists for it, and everything below
answers what happens instead of each of the others rather than leaving it unbuilt (FR-036).
**default** — not applicable: before `duration.normal` (200 ms) has elapsed nothing renders at all
(see the Duration rule below); once it has, the component goes straight to `loading` rather than
resting anywhere first, because it has no appearance independent of loading.
**hover / focus-visible / active** — not applicable: `Skeleton`'s blocks carry `aria-hidden` and sit
outside the tab order, so none can ever receive a pointer, keyboard or press event; the pulse keeps
running unchanged regardless of where the pointer or focus is.
**disabled** — not applicable: `Skeleton` is never an interactive control to disable; instead it
just holds its footprint until the content it stands in for replaces it.
**error** — not applicable to `Skeleton` itself: the caller's region owns the failure, and after the
10 s stall named in the Duration rule below it replaces the skeleton with a `danger` `Callout` and a
retry, rather than the skeleton ever painting an error appearance of its own.
**empty** — a skeleton with a zero count renders nothing. **selection / expansion** — not
applicable; a skeleton stands in for content that has neither state yet, and it never carries one
that content it replaces would not also have.
**Duration rule:** do not render before 200 ms (`motion.duration.normal`) have elapsed — a skeleton
that flashes is worse than a brief blank. After 10 s, the caller replaces it with a `danger`
`Callout` and a retry; a skeleton that pulses forever is a hang wearing a costume.

**Tokens** — `surface-sunken` fill. Radius `sm`. Motion `duration.slow`, `easing.standard` for the
pulse.

**Accessibility** — `aria-hidden` on the blocks this component renders, always; `Skeleton` itself
never carries `aria-busy` — it is the caller's own surrounding region (not this component) that
carries it, exactly once, no matter how many `Skeleton`s the region holds (T532, FR-054). A caller
that renders `Skeleton` more than once and puts `aria-busy` on each occurrence, or on each item of a
list, has reproduced the defect this rule exists to rule out — "a skeleton per cell announced per
cell is a screen reader reading the word 'loading' forty times for one table." `StatValue`'s own
spec section above records which component owns that single region for every composition of
`StatValue`/`Skeleton` this design system ships today. Under `prefers-reduced-motion: reduce` the
pulse stops on its resting frame.

**Acceptance** — skeleton footprint matches the loaded content within a couple of pixels, so the
before/after screenshots show no reflow; no text and no zero-placeholder appears inside a skeleton;
in a multi-line `text` skeleton, consecutive lines vary in width (60–90%) rather than repeating one
width — a token-correct skeleton that used a single fixed width for every line reads as a decorative
block rather than the shape of a paragraph, and fails this criterion (FR-063).

---

## Menu

**Purpose** — offer a short, known set of choices from a trigger, without leaving the page.

**Anatomy** — trigger button / popover surface / group label(s) / items (each: optional leading
selection glyph — `selection` variant only, present in every such item's markup, painted only when
checked — label, optional secondary line, optional trailing `Badge`, optional trailing item-action) /
separator / footer item.

**Variants** — `selection` (choosing one of a set; the current one is marked) and `actions` (each
item does something). The profile switcher is `selection` with an `actions` footer.

**Sizes** — one. Item height `space-12` (48px — touch minimum, and comfortable with a two-line
item). Surface min-width matches the trigger, max-width capped so labels wrap rather than truncate.

**States**

- **default** — surface `surface-raised`, boundary `border`, elevation `overlay`, radius `lg`.
- **hover** — item fill `surface-sunken`. `motion.duration.fast`.
- **focus-visible** — the focused item shows the standard focus ring inset within its bounds. Focus
  follows the roving item, never both trigger and item.
- **active** — item fill `surface-sunken` with boundary `border-strong` on the inline-start edge.
- **disabled** — a disabled item keeps focus (`aria-disabled="true"`, not the `disabled`
  attribute), shows `text-disabled`, and carries a reason on its secondary line.
- **loading** — an item whose action is in flight shows a spinner in its trailing slot and sets
  `aria-busy`. The menu stays open; other items become `aria-disabled` for the duration.
- **error** — the item action failed: the menu stays open, a `danger`-toned message renders inside
  the surface below the item, the item returns to `default`. Closing the menu on failure loses the
  message and is forbidden. Visually a `Callout`, but not the component itself (T559, FR-057):
  `role="menu"`'s required owned elements are `group`/`menuitem`/`menuitemcheckbox`/`menuitemradio`/
  `separator`, and `Callout` always carries `role="alert"`/`role="status"`, `aria-labelledby` and a
  focusable heading — every one of those independently makes it a disallowed owned element of
  `role="menu"`. The message renders as a plain, roleless paragraph instead, named by the failing
  item via `aria-describedby`; the assertive announcement `role="alert"` would have given for free
  is instead a dedicated `aria-live="assertive"` region that lives outside `role="menu"` entirely
  (a sibling, mounted for the whole popover's lifetime).
- **empty** — a menu with no items does not open; the trigger is `aria-disabled` with a reason. A
  menu that opens onto nothing is a dead end and reads as a bug.
- **selection** — the `selection` variant's shipping mechanism for the vocabulary's **selection**
  state (T569/T570, README's "Selection and expansion"; revised T572): the current item carries
  `role="menuitemradio"` and `aria-checked="true"`, and `Menu` itself paints the still-image mark for
  that state on every `selection`-variant item, regardless of what a caller supplies — a leading
  checkmark glyph, present when `checked` and holding the same, invisible-but-reserved width when
  not: a shape difference, never a fill or ink change alone. This mark lives in the primitive rather
  than in a caller-supplied slot because a caller cannot be trusted to supply it: T570 first shipped
  it as the `badge` slot's own content, "`Menu` itself does not decide what that slot contains," and
  T572 scenario 9 — a reader given only the built Storybook — found the predictable consequence:
  `Menu`'s own `Empty` and `ActionsWithDisabledItem` stories carry no badge at all, neither variant
  enforced one, and a checked item with no badge was pixel-identical to an unchecked one. That is
  T556's rule for a different component, applying here without exception: a decision a caller may
  not be trusted to write has to live somewhere that is not a caller. "Paint the selection mark"
  turned out to be exactly that kind of decision, not a wording choice a consumer should own.

  The `badge` slot each item may still carry (arbitrary content, the caller's own choice) is now an
  _additional_, optional signal, not the selection mark itself: it carries a different fact from
  "this is the checked item" — the identical, deliberate choice two consumers make is a plain
  `<Badge>Current</Badge>` rather than `variant="accent"`, at the item's _trailing_ edge, opposite
  the leading glyph so the two never occupy the same pixels: `SiteHeader`'s `ThemeControl` and
  `ProfileSummary`'s profile switcher (`site-header.md`, `profile-summary.md`). `accent` stays
  reserved for a different fact in both consumers (the item that is also _primary_ elsewhere in the
  product, e.g. a `Primary` profile); the checked-but-not-primary item is marked `Current` without
  borrowing `accent`'s meaning, which is what keeps the two facts distinguishable when both can be
  true of different items in the same list. `Menu`'s own stories (`ProfileSwitcher`, `Selection`)
  demonstrate the trailing slot with a plain, unstyled placeholder rather than a `Badge`, precisely
  because its wording is each consumer's decision — the leading glyph beside it is not a decision
  either consumer makes, or needs to.

- **expansion** — the trigger's own `aria-expanded`/`aria-haspopup="menu"` toggle is this package's
  one shipping case of the vocabulary's **expansion** state. The still-image evidence is not the
  trigger's own paint (which does not change) but what exists on the page: the popover panel is
  drawn beside the trigger when expanded, and is absent entirely when collapsed — never present but
  merely dimmed or scaled to zero.

**Tokens** — `surface-raised`, `surface-sunken`, `border`, `border-strong`, `text-primary`,
`text-secondary`, `text-disabled`, `focus-ring`, `overlay` (backdrop, mobile sheet only). Radius
`lg`. Elevation `overlay`. Motion `duration.fast`, `easing.decelerate`.

**Spacing** — surface padding-block `space-2`; item padding-inline `space-4`; label to secondary
line `space-1`; separator margin-block `space-2`.

**Responsive** — below `md`, the menu presents as a bottom sheet anchored to the viewport edge, full
width, with `overlay` behind it, so items stay within thumb reach. From `md` up, a popover anchored
to the trigger, flipping to the block-start side when it would overflow.

**Inline axis (M7 remediation, fourth-pass adversarial review).** The block-axis rule above says
nothing about the other axis, and the gap was real: a popover anchored `start-0` (the trigger's
inline-start edge) with no collision handling runs past the viewport's inline-end edge whenever the
trigger itself sits near that edge of its own container — measured on `ProfileSummary`'s Manage
trigger at 768 and 1280, where the surface ran to column 1279 of 1280 and 767 of 768, with the
trailing-slot `Spinner` an `unlink-in-flight` item paints (`MenuItemRow`, above) past the cut at
both widths. `align` (`MenuAlign` — `'start'` default, `'end'`) is the caller-set fix: a trigger a
caller knows sits at its own container's inline end passes `align="end"`, and the popover anchors
`end-0` instead, growing back toward the inline start rather than off the far edge. This is a static
per-trigger declaration a caller who knows their own layout makes, not a runtime viewport
measurement. A caller whose trigger's own inline-end position is not fixed relative to its container
(the common case, and every trigger in this package except a right-anchored one) leaves `align` at
its default.

**Accessibility** — trigger `aria-haspopup="menu"` and `aria-expanded`; surface `role="menu"`, items
`role="menuitemradio"` in the `selection` variant with `aria-checked` on the current one, otherwise
`role="menuitem"`. Keyboard: Enter / Space / ArrowDown open with the first (or checked) item
focused; ArrowUp / ArrowDown move with wrap; Home / End jump; Escape closes and returns focus to the
trigger; Tab closes and moves on. Focus is trapped only in the mobile sheet variant. Every item ≥
44px tall.

**Acceptance** — at 375px the menu is a full-width sheet with every row at least 44px tall; the
checked item is marked by its own leading checkmark glyph — present whether or not a caller supplies
a `badge` — never by colour alone, so the checked and unchecked rows in the same screenshot are two
visibly different shapes, not merely two different hues; a `badge` slot, where a consumer supplies
one, adds a second, independent signal beside that glyph (`<Badge>Current</Badge>` in `SiteHeader`
and `ProfileSummary`, a plain placeholder in `Menu`'s own stories) rather than standing in for it;
focus ring visible on the
focused item; the trigger regains focus after Escape; an item's label and its optional secondary
line are visibly distinguishable by size and colour (`type-body` in `text-primary` against a smaller
line in `text-secondary`) — a token-correct item that set both to the same size and ink would read
as one run-on line and fails this criterion (FR-063).

---

## Dialog

**Purpose** — force a decision on a single consequential action before it happens, blocking the
rest of the page until it is made.

**Anatomy** — backdrop / boxed surface / heading / body slot (arbitrary: paragraphs, an inline
`Callout`, or both) / two-`Button` action row.

**Variants** — none; every consumer supplies its own heading, body and action labels. Introduced by
T035b: `ConsentStep`'s withdrawal confirmation and the profile unlink confirmation were the same
markup maintained twice before it existed, so it is deliberately narrow — one heading, one body
slot, exactly two actions — rather than generalised further than either consumer needs.

**Sizes** — one: `max-w-sm`.

**States**

- **default** — backdrop `overlay`, surface `surface`, elevation `modal`, radius `xl` (`t-xl` on the
  sheet's top corners only below `md`, all four corners from `md` up).
- **focus-visible** — real, but its mount-time frame is not the one the still-image obligation
  (FR-037) is met with: opening the dialog moves focus straight to the heading (`tabIndex={-1}`) on
  mount, and the heading paints no ring of its own — its focus is for the accessible-name
  announcement, not a visible indicator — so that frame is byte-identical to `default` and
  documents nothing. The `FocusVisible` story instead forces the state a real Tab from the heading
  reaches next (`tests/visual/stories.spec.ts`'s `visualForceState`, driving Playwright's actual
  keyboard rather than a synthetic event neither Chromium's `:focus-visible` nor its own would
  match): focus on `primaryAction`, rendered first in the action row. That is the one visually
  distinct frame this state has to show, and it is a real stop on the trap's own path, not a
  fabricated one — Tab from there reaches `secondaryAction` and wraps from the last action back to
  the first without ever escaping to the page behind the backdrop, the one trap FR-049 permits and
  the trap this dialog owns rather than delegating. The visible ring at every step of that trap
  paints on whichever `Button` currently holds focus, per that component's own `focus-visible`
  answer above.
- **loading** — the action in flight sets `loading` and `loadingLabel` on its own `Button`; the
  other action disables via its own `disabled` rather than a dialog-wide flag, so a caller can
  disable one without the other.
- **error** — the caller renders a `Callout` in the body slot; the dialog itself has no error state.
- **empty / hover / active / disabled** — not applicable; a dialog with no actions is a malformed
  call site, and hover, active and disabled all belong to the `Button`s inside it — each one's own
  `disabled` prop, as `loading` above already uses to disable one action without the other — not to
  the dialog itself, which has no resting/pressed/disabled distinction independent of its actions.
- **selection** — not applicable; a dialog is not a set member.
- **expansion** — not applicable, and deliberately not the vocabulary's shipping case for this
  shape: a `Dialog` is open or closed by a caller-held boolean, not by an `aria-expanded` toggle on a
  trigger it owns, and it blocks the rest of the page rather than sitting beside it. `Menu`'s trigger
  (above) is where this package's one `aria-expanded` disclosure lives; `Dialog`'s open/closed switch
  is a different, mutually-exclusive-with-the-page shape and is fully covered by its own `default`
  state and the caller's `open` prop.

**Tokens** — `overlay` (backdrop), `surface` (fill), `text-primary` / `text-secondary` (heading /
body), `focus-ring`. Radius `xl`. Elevation `modal`.

**Spacing** — surface padding `space-6`; heading to body `space-3`; body to action row `space-6`;
between the two actions `space-3`.

**Responsive** — below `md`, a full-width bottom sheet anchored to the viewport edge. From `md` up,
a centred, boxed dialog. Both actions render at `lg` (48px) and stack full-width below `md`, sit
side by side from `md` up.

**Accessibility** — `role="dialog"` with `aria-modal="true"` and `aria-labelledby` pointing at the
heading; focus moves to the heading (`tabIndex={-1}`) on mount; Tab is trapped between the dialog's
own focusable elements; Escape calls the **secondary** action, never the primary one — the
accidental key must never be the one that takes the consequential path. The primary/secondary split
is about position and default styling, not about who owns Escape: Escape always goes to
`secondaryAction`, which is why that prop exists instead of a separate `onEscape`.

**Acceptance** — heading is focused and announced on open; Escape reaches the secondary action's
`onClick` and never the primary's; Tab cycles between exactly the dialog's own focusable elements
and never escapes to the page behind the backdrop; both actions render at least 44px tall; the
heading is visibly the most prominent text in the frame, larger and heavier than the body — a
token-correct dialog whose heading used the body's own type role would leave the reader unsure what
decision they are being asked to make, and fails this criterion (FR-063).

---

## StatValue

**Purpose** — present one number so it can be read, compared and trusted at a glance. This is the
component the whole product is judged on.

**Anatomy** — label / value / optional unit or suffix / optional delta / optional secondary line.

**Variants** — `hero` (a rating: value at font-size `3xl`), `compact` (a rank, a count: value at
`lg`), `inline` (within a table cell: value at `md`).

**Sizes** — as per variant; there is no independent size axis.

**States**

- **default** — label `text-secondary` at `sm`; value `text-primary`, `type-numeric` (T531/research
  D7 — the mono family plus `tabular-nums`, so alignment survives a change of the mono family),
  `semibold`, `tracking-tight`; delta `success` or `danger` **with an explicit sign character**,
  never colour alone; secondary line `text-secondary` at `xs`.
- **hover** — none on the value. If the surrounding row is interactive, the row owns hover.
- **focus-visible** — none unless the value is a link, in which case the standard ring applies to
  the link and the ring never crops the digits.
- **active** — none.
- **disabled** — none. A number is never dimmed to mean "not applicable"; if it does not apply, it
  is not rendered and the empty state below applies.
- **loading** — a `number` `Skeleton` of the value's exact footprint. **A loading `StatValue` never
  renders `0`, `–` or `--`.** In a stats tool a placeholder numeral read as real is the worst
  failure this design system can produce, and it is invisible in review because it looks fine.
- **error** — the last known value renders, with the secondary line stating when it was measured and
  that the refresh failed, plus a retry in the parent. Stale-and-labelled beats blank; blank beats
  wrong.
- **empty** — the value has never been observed (T532, US4 acceptance scenario 3, SC-010): render
  the reason **in words**, `type-supporting` (ordinary body/supporting typography, never
  `type-identifier` — this is prose stating a reason, not a raw value the product could not resolve
  to a name) in `text-secondary` at the value's own size, so the row keeps its footprint and the
  treatment is visibly distinct from a measured `text-primary`, `type-numeric` figure in colour,
  weight and typeface together. **Never a punctuation mark** (an em dash, `--`) a reader has to
  interpret — that was this state's own previous defect. The reason is a fact only the caller has
  (never played this leaderboard, not yet rated, no matches in the selected range); `StatValue`
  never invents one:
  - an explicit `emptyReason` prop always wins;
  - absent that, a `secondaryLine` the caller already supplied is **reused** as the value slot's own
    words — existing callers already pass the reason there, and it is not worth stating twice, so it
    is not repeated a second time beneath the value in this one case;
  - absent both, a generic, always-true default ("No data yet") renders — never a fabricated
    specific claim.
- **selection** — not applicable; a value is not a set member.
- **expansion** — not applicable; `StatValue` never truncates or reveals more of itself. A value that
  needs a longer explanation composes a `Tooltip` beside it (`tooltip.md`), which is that
  component's contract, not a state `StatValue` owns.

**Tokens** — `text-primary`, `text-secondary`, `success`, `danger`, `surface`, `surface-sunken`.
Font family `mono` for the value and any digit compared vertically, `sans` for labels and for the
`empty` state's own words. Sizes `xs`, `sm`, `md`, `lg`, `3xl`. Weights `normal`, `semibold`.
Tracking `tight` on the value.

**Spacing** — label to value `space-1`; value to delta `space-2`; value to secondary line `space-1`.

**Responsive** — `hero` drops to `2xl` below `md` only if it would otherwise wrap; it never
truncates and never shrinks below `2xl`.

**Accessibility** — label and value are associated (`<dt>`/`<dd>`, or a table header with `scope`).
A delta's sign is a character in the accessible name, not a rotated glyph: "+12" and "−8", not an
arrow. Values are text, never an image or a canvas. A `<dl>` may only directly contain
properly-ordered `dt`/`dd` groups (T559, FR-057): `secondaryLine`, when present, renders inside the
same `<dd>` as the value it qualifies, in its own row — never as a third element sibling to the
`dt`/`dd` pair, which is not a shape `<dl>` accepts (confirmed with axe-core's `definition-list`
rule; wrapping the trailing element in a bare `<div>` sibling does not clear it either, since the
check inspects what that `<div>` contains, not just its own tag name).

**Loading is announced once per region, never once per `StatValue` (T532, FR-054).** The `Skeleton`
this component renders while loading is `aria-hidden`, per `Skeleton`'s own contract below; nothing
in this component reads as data. Something must still tell assistive technology the region is busy,
and exactly one ancestor must do it: `announceLoading` (default `true`) puts `aria-busy="true"` on
this component's own `<dl>` while `status="loading"` — correct for a `StatValue` rendered standalone,
since nothing else would announce it. When several `StatValue`s are composed into one loading
column, row or table (a rating board, a match list), every one of them in that group is given
`announceLoading={false}`, and the **composing component** owns a single `aria-busy="true"` on the
shared container instead — never once per cell, which is the exact defect FR-054 names ("a skeleton
per cell announced per cell is a screen reader reading the word 'loading' forty times for one
table"). This is a standing obligation on any component that composes `StatValue` or `Skeleton`
directly; per-component application: `MatchList` (`MatchRow`), `MatchDetailPanel`, `AnalysisTimeline`
and `SearchBox` already own a single region each around their own `Skeleton`s; `ProfileSummary` owns
two independent regions (the identity block — avatar and alias — and the rating board), because the
two load independently; `FavouritesList`, `ArchivalControl`, `ReplayAvailabilityList` and
`SignInScreen`'s returning phase each own one region around their own loading list or block.

**Acceptance** — digits align vertically across stacked values in a screenshot (monospaced figures);
no gradient, texture or border passes behind a value; deltas show a sign character, including a
genuine zero delta ("+0"), which renders as data and is never suppressed; no `0` appears where data
has not loaded; an empty value states why in words, in `text-secondary`, never a zero and never a
punctuation mark; a region of stacked or tabled values announces "busy" once while loading, never
once per value; the value is visibly the most prominent element in its row — larger and heavier than
its own label — a token-correct `StatValue` that gave the label the value's own weight would compete
with the number for the first read, and fails this criterion (FR-063).
