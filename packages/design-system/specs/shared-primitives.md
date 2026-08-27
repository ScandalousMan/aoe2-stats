# Shared primitives

The three screen specs in this directory (`sign-in-screen`, `archival-control`, `profile-summary`) all
lean on the same six small components. They are specified once here so the three screens agree and
so no implementer has to invent a resting colour at eleven at night.

Each primitive below carries the nine sections in compressed form. Where a primitive grows a variant
a later feature needs, it earns its own file and this section becomes a stub pointing at it.

Read [`README.md`](./README.md) first: the contrast table and the token gap register are shared, and
nothing below restates them.

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
- **active** — `primary`: `accent-active`. Others: `surface-sunken` with boundary `border-strong`.
  No translate, no shadow change.
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

**Tokens** — colour `accent`, `accent-hover`, `accent-active`, `accent-contrast`, `surface`,
`surface-sunken`, `border`, `border-strong`, `text-primary`, `text-secondary`, `text-disabled`,
`danger`, `focus-ring`. Radius `md`. Font family `sans`, size `sm` / `md`, weight `semibold`.
Motion `duration.fast`, `easing.standard`. Elevation `none` — buttons do not float.

**Spacing** — icon-to-label `space-2`. Sibling buttons `space-3` apart.

**Responsive** — below `md`, a button that is the sole action of its block is full-width; siblings
stack vertically at `space-3`, recommended action first. From `md` up, buttons are intrinsic width
and sit on one row.

**Accessibility** — real `<button type="button">`, or `<a>` when it navigates (never a `<div>` with
a click handler). Space and Enter activate. Touch target ≥ 44px. Label contrast per the README
table; `accent-contrast` on `accent` in the light theme is the tightest pair `primary` depends on
and must be verified, not assumed.

**Acceptance** — exactly one `primary` per screenshot; focus ring visible and 2px offset from the
edge on the keyboard-focused button; the `primary` button's hover fill is visibly darker than its
resting fill and its active fill darker again, so the default, hover and active screenshots are
three distinguishable frames; loading button shows a spinner and the same width as at rest; disabled
button has visible explanatory text near it.

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
sign-in-screen), the heading takes `tabindex="-1"` and shows the standard focus ring.
**disabled** — none; a callout is never disabled. **loading** — none; a callout describes a settled
outcome. Anything still resolving is a `Skeleton`. **error** — `danger` is that state.
**empty** — a callout with no heading and no body renders **nothing at all**, not an empty bordered
box. This is the state that ships by accident, so the acceptance criteria test for it.

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
rather than present and blank.

---

## Badge

**Purpose** — mark one item in a list as being in a named state, at a glance.

**Anatomy** — root `<span>` / label text. No icon-only form.

**Variants** — `neutral` (fill `surface-sunken`, label `text-secondary`, boundary `border`),
`accent` (fill `surface-raised`, label `accent` in dark / `accent-active` in light — the README table
is why the light theme uses the darker token, and this is the one place `accent` appears as text).

**Sizes** — one: height `space-5`, padding-inline `space-2`, font-size `xs`, weight `semibold`,
tracking `wide`, radius `full`.

**States** — **default** only. No hover, no active, no focus: a badge is not interactive and must
never be the control that changes the state it names. **disabled / loading** — none; during a state
change the badge is replaced by a `Skeleton` of the same footprint. **error** — none.
**empty** — a badge with no label renders nothing.

**Tokens** — `surface-sunken`, `surface-raised`, `border`, `text-secondary`, `accent`,
`accent-active`. Radius `full`. Font size `xs`, weight `semibold`, tracking `wide`.

**Responsive** — identical at all viewports.

**Accessibility** — the label is real text, read in document order with the item it qualifies. Never
communicated by colour or shape alone.

**Acceptance** — the badge reads as a word at 375px without truncation; it is never the only
difference between two rows in a screenshot.

**Tone variants (US3, `capture-state-badge.md`)** — `Badge` grows four more variants,
`success` / `warning` / `danger` / `info`, each a `surface-raised` fill with a tone-coloured label
and a transparent boundary, the same shape `accent` already established. Full spec — including why
the fill stays neutral rather than tone-tinted, and the one theme-branching exception `accent`
needed that these four do not — lives in
[`capture-state-badge.md`](./capture-state-badge.md#5-badge-tone-variants-new-added-to-shared-primitivesmds-badge),
which is also where `CaptureStateBadge`, the composite that actually chooses a tone, is specified.

---

## Skeleton

**Purpose** — hold the shape of content that is arriving, so nothing jumps when it lands.

**Anatomy** — one or more blocks, each matching the footprint of the element it stands in for.

**Variants** — `text` (height matching a line-height token, width 60–90% varied per line), `number`
(the exact footprint of the numeral it replaces), `block`.

**Sizes** — derived from the content, never chosen freely.

**States** — **loading** is the only state; the component exists for it. It has no hover, focus,
active, disabled or error state. **empty** — a skeleton with a zero count renders nothing.
**Duration rule:** do not render before 200 ms (`motion.duration.normal`) have elapsed — a skeleton
that flashes is worse than a brief blank. After 10 s, the caller replaces it with a `danger`
`Callout` and a retry; a skeleton that pulses forever is a hang wearing a costume.

**Tokens** — `surface-sunken` fill. Radius `sm`. Motion `duration.slow`, `easing.standard` for the
pulse.

**Accessibility** — container carries `aria-busy="true"` and `aria-hidden` on the blocks themselves;
the region announces once, not per block. Under `prefers-reduced-motion: reduce` the pulse stops on
its resting frame.

**Acceptance** — skeleton footprint matches the loaded content within a couple of pixels, so the
before/after screenshots show no reflow; no text and no zero-placeholder appears inside a skeleton.

---

## Menu

**Purpose** — offer a short, known set of choices from a trigger, without leaving the page.

**Anatomy** — trigger button / popover surface / group label(s) / items (each: label, optional
secondary line, optional trailing `Badge`, optional trailing item-action) / separator / footer item.

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
- **error** — the item action failed: the menu stays open, a `danger` `Callout` renders inside the
  surface below the item, the item returns to `default`. Closing the menu on failure loses the
  message and is forbidden.
- **empty** — a menu with no items does not open; the trigger is `aria-disabled` with a reason. A
  menu that opens onto nothing is a dead end and reads as a bug.

**Tokens** — `surface-raised`, `surface-sunken`, `border`, `border-strong`, `text-primary`,
`text-secondary`, `text-disabled`, `focus-ring`, `overlay` (backdrop, mobile sheet only). Radius
`lg`. Elevation `overlay`. Motion `duration.fast`, `easing.decelerate`.

**Spacing** — surface padding-block `space-2`; item padding-inline `space-4`; label to secondary
line `space-1`; separator margin-block `space-2`.

**Responsive** — below `md`, the menu presents as a bottom sheet anchored to the viewport edge, full
width, with `overlay` behind it, so items stay within thumb reach. From `md` up, a popover anchored
to the trigger, flipping to the block-start side when it would overflow.

**Accessibility** — trigger `aria-haspopup="menu"` and `aria-expanded`; surface `role="menu"`, items
`role="menuitemradio"` in the `selection` variant with `aria-checked` on the current one, otherwise
`role="menuitem"`. Keyboard: Enter / Space / ArrowDown open with the first (or checked) item
focused; ArrowUp / ArrowDown move with wrap; Home / End jump; Escape closes and returns focus to the
trigger; Tab closes and moves on. Focus is trapped only in the mobile sheet variant. Every item ≥
44px tall.

**Acceptance** — at 375px the menu is a full-width sheet with every row at least 44px tall; the
checked item is marked by text or a `Badge`, not by colour alone; focus ring visible on the focused
item; the trigger regains focus after Escape.

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
- **loading** — the action in flight sets `loading` and `loadingLabel` on its own `Button`; the
  other action disables via its own `disabled` rather than a dialog-wide flag, so a caller can
  disable one without the other.
- **error** — the caller renders a `Callout` in the body slot; the dialog itself has no error state.
- **empty / hover / active** — not applicable; a dialog with no actions is a malformed call site,
  and hover/active belong to the `Button`s inside it, not to the dialog itself.

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
and never escapes to the page behind the backdrop; both actions render at least 44px tall.

---

## StatValue

**Purpose** — present one number so it can be read, compared and trusted at a glance. This is the
component the whole product is judged on.

**Anatomy** — label / value / optional unit or suffix / optional delta / optional secondary line.

**Variants** — `hero` (a rating: value at font-size `3xl`), `compact` (a rank, a count: value at
`lg`), `inline` (within a table cell: value at `md`).

**Sizes** — as per variant; there is no independent size axis.

**States**

- **default** — label `text-secondary` at `sm`; value `text-primary`, `font-mono`, `semibold`,
  `tracking-tight`; delta `success` or `danger` **with an explicit sign character**, never colour
  alone; secondary line `text-secondary` at `xs`.
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
- **empty** — the value has never been observed: render the label with an em dash in
  `text-secondary` at the value's size, and a secondary line saying why in plain words. The em dash
  is `text-secondary`, so it cannot be mistaken for a measured `text-primary` figure.

**Tokens** — `text-primary`, `text-secondary`, `success`, `danger`, `surface`, `surface-sunken`.
Font family `mono` for the value and any digit compared vertically, `sans` for labels. Sizes `xs`,
`sm`, `md`, `lg`, `3xl`. Weights `normal`, `semibold`. Tracking `tight` on the value.

**Spacing** — label to value `space-1`; value to delta `space-2`; value to secondary line `space-1`.

**Responsive** — `hero` drops to `2xl` below `md` only if it would otherwise wrap; it never
truncates and never shrinks below `2xl`.

**Accessibility** — label and value are associated (`<dt>`/`<dd>`, or a table header with `scope`).
A delta's sign is a character in the accessible name, not a rotated glyph: "+12" and "−8", not an
arrow. Values are text, never an image or a canvas.

**Acceptance** — digits align vertically across stacked values in a screenshot (monospaced figures);
no gradient, texture or border passes behind a value; deltas show a sign character; no `0` appears
where data has not loaded; an empty value shows a secondary-colour em dash with an explanation, not
a zero.
