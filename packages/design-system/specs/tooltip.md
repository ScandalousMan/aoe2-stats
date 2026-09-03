# Tooltip

**Component**: `src/components/Tooltip/` (T456)
**Feature**: 004, Phase 8 — first consumed by [`country-flag.md`](./country-flag.md) §11, itself
consumed by `ProfileSummary`'s `IdentityBar` ([`profile-summary.md`](./profile-summary.md) §13).
**Requirements**: FR-008 (the country name "MUST be conveyed through a design-system Tooltip on the
flag — revealed on hover and on keyboard focus, with an accessible name for assistive technology"),
FR-013 (tokens only, a story, visual regression). SC-002.
**Depends on**: [`README.md`](./README.md) — the measured contrast pairs and the gap register. Gaps
in play: **DS-4** (focus-ring width and offset), **DS-6** (max-width / reading measure).
**Asset origin** (README rule 3): none. This component draws no image, no glyph and no caret. It is
a surface with text on it.

## 1. Purpose

Give one small, non-essential fact a home that costs no horizontal space in a dense row — revealed
on hover, on keyboard focus and on tap, and always present to assistive technology whether it is
revealed or not.

## 2. Anatomy

```
Tooltip                    a trigger and its content; never a free-floating surface
├─ Trigger    the caller's element, made a real <button type="button"> by this component.
│             Exactly one child. It is a tab stop, it has a ≥44px hit area, and pressing it
│             pins the content open (§4 active) — that is the whole of what it does
└─ Content    role="tooltip". ALWAYS in the DOM, `hidden` when closed (§8 — this is what makes
   │          the accessible name resolve without the tooltip ever being opened)
   ├─ Qualifier  optional, visually hidden — what the value is a value OF ("Country: ")
   └─ Value      the visible text
```

**Three rules the rest of this file is the consequence of.**

1. **A tooltip is never the only carrier of the fact** (README rule 4). The content element is in the
   DOM at all times and is wired to the trigger's accessible name or description (§8), so a screen
   reader reaches the fact without a hover event, which it cannot produce. A tooltip whose content
   is mounted on open is a fact that exists only for a sighted pointer user, and that is the defect
   this component is most likely to ship with.
2. **A tooltip carries only what a reader can afford to miss.** No number, no status, no error, no
   action, no link, no form control, no second sentence. Anything a user must act on is a
   `Callout`; anything they must compare is a `StatValue` on the page. Content that only appears
   under a pointer cannot be read, compared or copied, and this product is judged on numbers being
   all three (README rule 1).
3. **The content surface never covers a figure.** Default placement is **block-start** (§3) for
   exactly this reason: the first consumer's trigger sits in an identity bar with the rating board
   directly beneath it, and a surface that drops down over the ratings is README rule 1 broken by
   position instead of by style.

**No caret, no arrow, no tail.** The association is carried by proximity (`space-2` from the
trigger, §6) and by the trigger being visibly focused or hovered at the same moment. A caret is one
more thing to mis-place against a flipped or shifted surface, and it buys nothing a 44px trigger
`space-2` away does not already say.

**No portal.** The content renders as a positioned sibling of the trigger, inside the caller's own
DOM, so it inherits the theme without a second theme root and needs no `z-index` — see §3a.

## 3. Variants and sizes

**No tone variants.** There is no `danger` or `warning` tooltip: a tooltip that turns red is an
error message that disappears when the pointer moves, which is the one place an error must never be.
`Callout` owns tone.

**One size.** Content is `sm` `sans`, weight normal, in `text-primary`. It does not scale with the
trigger: a tooltip on a 16px flag and one on a 24px flag are the same tooltip, because the text in
them is read at reading size or it is not read.

Two props change behaviour rather than appearance, and both are named here because an implementer
would otherwise invent one of them:

| Prop        | Values                                      | Meaning                                                                                                                      |
| ----------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `relation`  | `"label"` _(default)_ / `"describe"`        | Whether the content **is** the trigger's accessible name (`aria-labelledby`) or **adds to** it (`aria-describedby`) — §8     |
| `placement` | `"block-start"` _(default)_ / `"block-end"` | The preferred side. Both flip to the other when the preferred side would overflow the viewport; neither is a guarantee (§3a) |

`relation="label"` is the default because the case this component exists for is a trigger whose only
visible content is an image. A trigger that already has a text label takes `relation="describe"`;
a trigger with a text label AND `relation="label"` is a call-site bug — it replaces the label the
user can see with one they cannot, and WCAG 2.5.3 fails the moment the two differ.

### 3a. Placement, flipping and stacking

- **Preferred side, then the opposite one.** `block-start` is tried first; if the surface would cross
  the viewport's block-start edge it flips to `block-end`. There is no third position and no
  inline-axis placement: a tooltip beside a 24px mark in a wrapping row is a surface that changes
  side as the line rewraps, and a reviewer cannot tell that from a defect.
- **The surface shifts along the inline axis** to stay at least `space-4` from both viewport edges,
  centred on the trigger otherwise. It shifts; it never shrinks below its content and never
  truncates (§7).
- **It reflows on scroll and resize; it does not close on either.** WCAG 1.4.13's persistence
  requirement is that content stays until hover or focus is removed, and a tooltip that vanishes
  because the page moved a pixel under a trackpad is the same bug as one that closes on a timer.
- **No `z-index`, and none is needed.** The surface is absolutely positioned, so it paints above the
  non-positioned content that follows it — which is what the rating board beneath the first
  consumer's identity bar is. Two constraints the caller owes rather than this component: no
  ancestor between the trigger and the page root may clip overflow, and no **later** positioned
  sibling may sit over the surface's box. `ProfileSummary` satisfies both today. If a call site ever
  cannot, that is a stacking token this system does not have, and it enters README's gap register
  then rather than being solved with an arbitrary number now.

## 4. States

All eight, and **four of them are invisible to a screenshot** — the reason T456 owes an interaction
test and not only a story capture, and the reason this section names each one rather than grouping
them.

- **default (closed)** — nothing is visible. The content element is in the DOM with the `hidden`
  attribute. The trigger renders exactly as its caller drew it, with no dotted underline, no "?"
  affix, no cursor change beyond `cursor: default` — a tooltip does not advertise itself, because a
  fact worth advertising belongs on the page.
- **hover (open)** — pointer enters the trigger: the content opens after `motion.duration.normal`.
  The delay is deliberate and is the only delay in the component: a pointer crossing an identity bar
  on its way to the ratings must not strobe a surface open and shut behind it. **The surface itself
  is hoverable** (WCAG 1.4.13): moving the pointer from the trigger onto the content keeps it open,
  and it closes `motion.duration.fast` after the pointer has left **both**. That grace is what makes
  the `space-2` gap crossable.
- **focus-visible (open)** — the trigger receives focus via the keyboard: the content opens
  **immediately, with no delay at all.** The hover delay exists to suppress pointer noise; a
  keyboard user did not create any, and charging them 200 ms of latency per Tab stop is a cost with
  no cause. Two further rules, both of which a reviewer will assume were handled and neither of which
  a static snapshot can show:
  - **The trigger's own focus ring still renders** — `outline-2 outline-offset-2` in `focus-ring`,
    the one uniform ring (gap DS-4), unclipped, in both themes. The tooltip appearing is **not** a
    substitute for the ring: a user who tabs past this trigger must be able to see where focus is
    even if the surface is off-screen, flipped, or suppressed by a dismiss (below).
  - **`:focus-visible`, not `:focus`.** A pointer click that focuses the trigger must not leave a
    tooltip stranded open after the pointer has gone; hover already covers that user. Focus arriving
    by keyboard, by `autofocus` restoration or by a programmatic `focus()` from a skip link all open
    it; a mouse-down does not.
- **active (open, pinned)** — the trigger is pressed (click, Enter, Space, or a tap). The content
  opens with no delay and **stays open until an explicit dismiss** (below), independent of the
  pointer. This is the only route a touch user has, since touch produces no hover and generally no
  `:focus-visible`, and without it the fact is unreachable on the viewport where the trigger is
  hardest to read. The trigger shows its own pressed treatment (its `Button` state); the surface does
  not move, scale or change on press.

  **The three open sources are independent and OR together.** The tooltip is open while hover, focus
  or pin is true, and closes when the last one ends. Pressing a trigger that is already open by hover
  does not toggle it shut — an open-then-immediately-closed tooltip under a tap reads as a
  misfire, so a second press on a pinned tooltip is what closes it and a press on a hovered one only
  pins.

- **disabled** — **the trigger is never the `disabled` attribute.** A `disabled` button is neither
  focusable nor hoverable in any browser, so disabling it is exactly the act that makes the
  explanation unreachable at the moment it is most wanted. A caller with a non-actionable trigger
  uses `aria-disabled="true"`, keeps the tab stop, and the tooltip behaves as specified. The surface
  itself is never disabled and never dimmed: `text-disabled` is below AA by design (gap DS-3) and
  this text may be a fact's only visible form.
- **loading** — the content has not arrived: **the tooltip does not exist yet.** No empty surface, no
  spinner inside one, no "Loading…", no `Skeleton` in a popover. The trigger renders as a plain,
  non-interactive element with no tab stop until content exists, and gains its button semantics when
  it does. A tab stop that opens onto nothing is `Menu`'s "a menu that opens onto nothing is a dead
  end" applied one component down.
- **error** — none of its own. Content that failed to resolve is content that is absent, and absent
  content is the empty state below. A tooltip never reports its own failure: the user cannot act on
  it, and a surface saying "could not load" over a rating board is worse than the silence it
  replaces (`profile-summary.md` §12.7's identical rule for a flag image that fails).
- **empty** — content that is absent, `null`, or **blank after trimming**: the component renders
  **the trigger's child alone**, unwrapped — no `<button>`, no tab stop, no `aria-labelledby`, no
  `role="tooltip"` element, no zero-size surface. The blank-after-trimming case is the one that
  actually ships: an API that types a field as a non-null string delivers `""`, and a component that
  tests only for `undefined` mounts a focusable control that opens an empty box. **The test is
  emptiness, not nullishness** (`profile-summary.md` §12.3 settled the same trap for the alias).

## 5. Tokens used

Colour: `surface-raised` (the surface fill — **opaque, never translucent**: this surface crosses over
text and over figures while it is open, and a translucent one renders text on text), `border` (the
1px hairline, decorative per README's own rule for that token — the surface's meaning is its words,
so its boundary carries none), `text-primary` (the content), `focus-ring` (the trigger's ring, on
whatever background the caller paints; `ProfileSummary`'s root is `bg-background`, so the measured
pair there is `focus-ring` on `background`).

`text-primary` on `surface-raised` is 14.5 light / 12.0 dark in README's table — the same pair
`Callout` body text rides on, and the widest margin available in this system. It is chosen over
`text-secondary` deliberately: this text may be the only visible form of the fact, so it takes the
primary ink even though it is a secondary fact.

Typography: `sans`, size `sm`, weight normal, no tracking change. **Never `mono`, and never a
figure.** A tooltip carries prose (rule 2); the day one carries a number is the day the number is on
the wrong surface.

Radius `md` — the same corner as a `Button`, one step under `Callout`'s and `Menu`'s `lg`, because
this is the smallest surface in the system and `lg` on a two-word box reads as a pill.

Elevation `overlay` — the same token `Menu`'s popover takes, and for the same reason: it is
temporarily above the page rather than part of it. Not `modal`; nothing is blocked behind it.

Motion: opacity only. Open — `motion.duration.fast` with `easing.decelerate`. Close —
`motion.duration.instant`: a surface fading out over a rating the user is already reading is worse
than one that is simply gone. **No translate, no scale, no shadow animation, and never a layout
property**; the surface arrives at its final position at full size and only its opacity moves.
Under `prefers-reduced-motion: reduce`, both directions are `motion.duration.instant` (README
rule 5).

**No new token and no new gap.** DS-4 supplies the ring's interim, DS-6 the max-width's.

## 6. Spacing

| Between                                        | Step                                                      |
| ---------------------------------------------- | --------------------------------------------------------- |
| Trigger edge to surface edge (the offset)      | `space-2`                                                 |
| Surface padding-inline                         | `space-2`                                                 |
| Surface padding-block                          | `space-1`                                                 |
| Surface to the nearest viewport edge (minimum) | `space-4`                                                 |
| Trigger hit area                               | `icon-xl` (44px) minimum in both axes, reached by padding |

The trigger's hit area is extended **by padding on the trigger itself**, never by a transparent
overlay element — `Button`'s existing rule, for the same reason: an overlay intercepts events its
sibling was supposed to get, and it is invisible in review.

The tooltip adds **no** outer margin and no reserved space in flow: the surface is out of flow
entirely, so opening it moves nothing. Overlaying the closed and open screenshots must show every
element in the same position (§10).

## 7. Responsive

- **375** — there is no hover. The press-to-pin route (§4 active) is the only one, which is why it is
  specified rather than optional. The trigger is ≥44px here above all. The surface's inline size is
  capped at the viewport minus `space-4` on each side and it **shifts** to fit; it never overflows
  and never gains a horizontal scrollbar.
- **768 / 1280** — hover, focus and pin all apply. The surface is capped at DS-6's `max-w-xs` and
  wraps onto a second line rather than truncating.
- **Text wraps; it is never truncated, ellipsised or clipped, at any viewport.** A tooltip is text
  the reader cannot select, copy or scroll — an ellipsis in it is a fact they have no route to. This
  is `profile-summary.md` §12.8's "a truncated identifier is a wrong identifier" applied to prose.
- **200% zoom / 320px logical width** — everything here is rem-sized and grows with the text; the
  surface re-shifts and re-flips against the zoomed viewport rather than being clipped by it.

## 8. Accessibility

- Surface: `role="tooltip"` with a stable generated id (`useId`). It is **never** focusable, never a
  tab stop, contains no interactive element, and is not an `aria-live` region — it is announced
  through its relationship to the trigger, and announcing it twice is worse than once.
- **The content element is in the DOM whenever the component renders**, carrying the `hidden`
  attribute while closed. Accessible-name computation reads a referenced hidden element, so the
  trigger is named or described correctly **without the tooltip ever being opened** — which is the
  literal text of FR-008's "with an accessible name for assistive technology", and the single
  requirement of this spec most likely to be lost to a mount-on-open implementation that looks and
  screenshots identically.
- Trigger: a real `<button type="button">`. `relation="label"` → `aria-labelledby` pointing at the
  content element. `relation="describe"` → `aria-describedby` pointing at it, with the trigger's own
  label untouched. Never `title` — its timing, styling and touch behaviour are the browser's, and
  this spec would be describing something it does not control.
- **Where the value alone is ambiguous, the content carries a visually hidden qualifier** naming what
  it is a value of, so the accessible name is "Country: France" and not the bare "France, button".
  This is `match-history.md` §11.2's rule ("a label prefix that says what it is an id of") applied to
  a name instead of an id. The visible text stays the bare value and is contained in the accessible
  name, so WCAG 2.5.3 (label in name) holds.
- Keyboard, in full:
  - **Tab** moves to the trigger and opens the tooltip (`:focus-visible`); **Tab** again moves on and
    closes it. Focus is never trapped and never moved by this component.
  - **Enter / Space** pin and unpin (§4 active). No other key activates it.
  - **Escape** dismisses the tooltip **while leaving focus on the trigger**, and it stays dismissed
    until focus leaves and returns, or the pointer re-enters. This is WCAG 1.4.13's "dismissible",
    and the "stays dismissed" half is the part that gets dropped: an Escape that is immediately
    undone by the focus still sitting there has dismissed nothing.
  - No arrow-key behaviour, no Home/End, no roving. This is one control, not a collection.
- Touch: tap pins, tap elsewhere dismisses. A tap that dismisses a pinned tooltip does **not** also
  activate whatever it landed on — the first tap outside is spent on the dismiss.
- Contrast: `text-primary` on `surface-raised` (README's table, both themes). The `border` hairline
  is decorative and exempt from 1.4.11 — the surface is not a control. `focus-ring` on the caller's
  background clears the 3:1 non-text floor per README.
- Colour is never the only carrier: the surface's meaning is its words, and greyscaling it loses
  nothing (README rule 4).
- Never used to hold a required instruction, an error, an action, or the only copy of a number
  (§2 rule 2). A fact that must be read is on the page.

## 9. Where this component may and may not appear in 004

**`CountryFlag` only** ([`country-flag.md`](./country-flag.md) §11), consumed through
`ProfileSummary`'s `IdentityBar`. Stating the boundary is what stops the next dense row from
answering "it does not fit" with a tooltip:

- **Not on a `StatValue`, a rating, a rank, a delta or any figure** — README rule 1. A number under a
  pointer is a number nobody compared.
- **Not on `MatchRow`'s civilisation, map or player colour.** `match-history.md` §12.3 caps what a row
  shows; each of those marks already carries its name as adjacent text, and a tooltip would be a
  second, hover-only copy of a fact already on screen.
- **Not on a `Button` to explain what the button does.** A button that needs a tooltip needs a better
  label.
- **Not on a disabled control to say why it is disabled.** `Button`'s own rule already requires that
  reason to be visible text in `text-secondary`, and §4 disabled is why a tooltip could not carry it
  anyway.

## 10. Visual acceptance criteria

Four of the eight states are pointer- or keyboard-only, so **these criteria are judged against
stories that force the state open** (a play function or a pseudo-state story), not against a default
capture. A criterion below that says "the open story" means such a story; a suite that has only
closed captures has verified none of this and passes anyway, which is the failure mode this list is
shaped against.

**The reveal, on both routes**

- [ ] **The hover story** shows the surface open with the pointer over the trigger, in both themes.
- [ ] **The keyboard-focus story** shows the surface open with the trigger reached by Tab — and the
      trigger's **focus ring is visible and unclipped in the same frame**. A frame with the tooltip
      open and no ring on the trigger fails this criterion.
- [ ] The hover-open and focus-open frames show the **same surface in the same position** —
      overlaying them differs only in the trigger's focus ring.
- [ ] **The pinned (pressed) story** shows the surface open with no pointer over the trigger and no
      focus ring — the touch route.

**The dismiss**

- [ ] The after-Escape story shows **no surface**, and the trigger still visibly focused: the ring is
      in the frame and the tooltip is not.
- [ ] The after-blur story shows no surface anywhere in the frame.
- [ ] No story shows a surface with the pointer neither on the trigger nor on the surface, unless it
      is the pinned story.

**Placement and what it must not cover**

- [ ] In the open story, the surface sits **above** the trigger and does not overlap any figure in the
      frame; nothing behind the surface shows through it (it is opaque in both themes).
- [ ] In a story with the trigger near the viewport's top edge, the surface has flipped **below** it
      and is fully within the frame.
- [ ] At 375 the surface is fully within the viewport with at least `space-4` clear of both edges, and
      the page shows no horizontal scrollbar.
- [ ] The surface never contains a truncation or an ellipsis; the long-content story wraps onto a
      second line.

**Craft, and the things that must not move**

- [ ] Overlaying the closed and open stories, **every element on the page is in the identical
      position** — opening the tooltip reflows nothing.
- [ ] The trigger's hit area is at least 44×44px in the open story at 375 (measurable from the
      element box, not from the mark drawn inside it).
- [ ] No caret, arrow, tail, dotted underline or "?" affix appears in any story.
- [ ] No figure, no monospaced text and no `danger`/`warning` tone appears inside any surface.
- [ ] Converting the open story to greyscale leaves the content fully readable.
- [ ] Under `prefers-reduced-motion: reduce` the surface is fully opaque in the first captured frame
      after the state is forced — nothing is caught mid-fade.
- [ ] The empty-content story renders **no button and no surface**: the trigger's child alone, and
      tabbing through the story does not stop on it.
