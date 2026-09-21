# ArchivalControl

**Component**: `src/components/ArchivalControl/`
**Feature**: 001, US1 and US5 — consumed by `apps/web/src/features/profile/` (T037, rewired by
T407) and the privacy route
**Requirements**: FR-006 (the identity statement), FR-034, FR-035, FR-041. Constitution IX (4.0.0).
**Tier**: screen (`src/screens/`).
**Surface class**: `prose` (README's "Surface density" section) — the identity statement and basis
statement are continuous reading text, `space-3` between the statements in one block and `space-8`
between the two subjects, the class's own paragraph and section rhythm.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`.

**Amended 2026-08-27 (T406) — rebuilt from `ConsentStep`, constitution IX 4.0.0.** IX no longer
lets ingestion wait on a decision: archival of a linked user's own recordings runs on legitimate
interest (Art. 6-1-f) and is on by default, including for a user who has never answered any
question. What replaced consent is a standing right to object (Art. 21). This component used to
ask permission before archiving — an `onboarding` variant with an Accept/Decline pair gating the
first capture — and that variant **is the retired gate in visual form**. It is gone. What remains
states that archival is running, on what basis, and offers the one switch (object, or resume) that
changes it. `ConsentStep` is the name this file and component carried before the rename; nothing
below describes it.

**Why there is no confirmation step before objecting**, unlike the `onboarding`/`withdraw-confirm`
pair this replaces: the previous design asked for a second confirmation before turning archival off
because turning it off _reversed a grant the user had just made_. Objecting reverses nothing — it
exercises a standing right that was already true this whole time, the same right resuming exercises
in the other direction. `docs/privacy/processing-register.md`'s balancing test for this activity
calls the objection route "a one-action way out"; a confirmation dialog in front of it would be
exactly the friction that phrase rules out, re-imposing a decision-before-effect shape the amendment
retired. `withdraw-confirm` does not survive into this file for that reason, not because the anatomy
happened to change.

## 1. Purpose

Tell the user, in one place, that we archive their replays by default and why — before telling them,
separately, that their Steam account is the only way in and that there is no way back if they lose
it — and give them the one control that stops or resumes it.

## 2. Anatomy

```
ArchivalControl
├─ Heading                    h2
├─ IdentityStatement          FR-006. Four statements + one rationale line. Always visible, full
│  ├─ StatementHeading        form — unaffected by the 4.0.0 amendment and unchanged from the
│  ├─ Statement ×4             component this replaces.
│  └─ RationaleLine
├─ BasisStatement              what we archive, on what basis, and the boundary of objecting
│  ├─ BasisHeading             h3
│  └─ Paragraph ×7             mechanism (5), legal basis (1), the objection boundary (1)
├─ StatusRegion                Callout — current state, and the one switch
│  ├─ Callout/success           state = "archiving"
│  └─ Callout/info               state = "objected"
├─ PrivacyNoticeLink           FR-041 — a Link at variant="standalone" (§5.1), never a local anchor
└─ WriteFailedRegion           Callout/danger ×0..1 — the write failed
```

The `IdentityStatement` is the first block after the heading, exactly as before. It is not in an
accordion, not in a tooltip, not behind "Learn more", not below the fold on a phone, and not in a
smaller or lighter type than the basis statement. FR-006 says "stated plainly"; anatomy is how that
becomes checkable, and none of it changed when the consent gate did.

## 3. Variants and sizes, states and props

**Variants and sizes** — one variant, no size split, no dialog. The state vocabulary is now the same
shape everywhere it is used, so there is nothing left for a `variant` prop to select.

`state: 'archiving' | 'objected'` — the only two facts `archival_objected_at` can mean
(`contracts/http-api.md`'s `GET /api/me`). There is no third, "unanswered", state: a user who has
never touched the switch **is** `'archiving'`, indistinguishably from one who objected and later
resumed — the data model records no timestamp for a resumption (`archival_objected_at` returns to
`null` either way), and this component does not invent a distinction the API cannot answer on the
next page load.

- **`archiving`, default** — no story-local acknowledgement. The steady state a page load lands on,
  whether the user has never touched the switch or resumed a long time ago.
- **`archiving`, `justResumed`** — the caller sets this immediately after its own `onResume` call
  resolves, in the same session, so the person who just pressed the button sees that it worked
  before the callout collapses back to the plain steady state on the next reload. This is the one
  place the "never answered" and "explicitly resumed" cases render differently, and it is
  deliberately ephemeral: nothing is stored that would let a later page load reconstruct it, so the
  component does not pretend otherwise.
- **`objected`** — `objectedAt` (required whenever `state="objected"`; the API always returns a
  timestamp for this state) renders the date the objection was recorded.

```
loading?: boolean            // before /api/me resolves — StatusRegion only; IdentityStatement and
                              // BasisStatement are static copy, never skeletoned
submitting?: boolean         // the switch write is in flight; the one visible button disables and
                              // shows its loading label
writeFailed?: boolean        // the write failed; WriteFailedRegion renders, state is unchanged
unavailable?: boolean        // the route is unreachable; the switch disables, an info callout says so
onObject?: () => void        // state="archiving" only
onResume?: () => void        // state="objected" only
privacyNoticeHref?: string
```

There is deliberately no `onConfirmWithdraw` / `onCancelWithdraw` pair and no `withdraw-confirm`
render path — see the amendment note above. `onObject` and `onResume` are named for the action
performed, not reused from a grant/decline vocabulary that no longer describes anything this
component does.

## 4. Copy

Normative. The implementer copies these strings; they are not placeholders. If product wants them
changed, the change happens in this file first.

### 4.1 Identity statement (FR-006) — unchanged

`StatementHeading`: **Before you decide: how you get back in**

1. Your Steam account is the only key to this account. There is no password.
2. If you lose access to your Steam account, you lose access here. We cannot let you back in.
3. There is no password reset, no email verification and no account recovery — not through support,
   not by proving who you are, not by any other route.
4. Getting a Steam account back is between you and Valve. We are not part of that.

`RationaleLine`, last and never first: _We never store a password, so there is nothing here to
steal and nothing to reset. That is the trade._

**Banned in this block**, and each one is checkable in review — carried over unchanged:

- Reassurance framing: "don't worry", "rest assured", "for your security", "we've got you covered",
  "this keeps your account safe".
- Any suggestion that a human can help: "contact us if you lose access", "we'll do our best",
  "get in touch and we'll sort it out". There is no such route. Saying otherwise is the specific
  lie FR-006 exists to prevent.
- Hedging: "you may not be able to", "it might not be possible to recover". It is not possible.
- Any of the four statements behind a disclosure, a tooltip, a `title` attribute, a scroll-to-reveal
  or a "Learn more".
- A shield, lock or tick icon anywhere in the block. An icon that reads as a safety badge reframes a
  limitation as a feature.
- `text-secondary`, `text-disabled` or a font-size below `md` on any of the four statements.
  Grey-on-grey de-emphasis is burial by other means.
- Placing the block after `StatusRegion`, or after the basis statement.

The `StatementHeading` still reads "Before you decide" even though there is no longer a decision to
make before archival starts — it is left as-is because it is true of the one decision that remains
in this component's reach, objecting, and because rewording a normative, banned-phrase-checked block
is exactly the kind of drive-by edit this section exists to prevent. If a future change wants
different wording here, it is a deliberate edit to this file, not a side effect of this one.

### 4.2 Basis statement

`BasisHeading`: **What we archive, and why**

1. This runs on our legitimate interest in saving your matches before Microsoft deletes them, not
   on your consent (GDPR Art. 6-1-f). Nothing is asked of you before it starts.
2. Age of Empires II deletes your replay files about 31 days after the match. After that nobody can
   get them back — not you, not us, not Microsoft.
3. We download the recording of each of your matches from your own point of view and keep the
   original file, unchanged.
4. We only ever take your own point of view, never another player's.
5. This runs by itself. You never have to remember to do anything.
6. It covers every Steam account you have linked, so no linked profile quietly expires.
7. You can object at any time (GDPR Art. 21). Objecting stops future captures immediately; it does
   not touch your match history, your ratings, or replays already archived — and does not go back
   and capture what was missed while you had objected, either.

Paragraph 7 is the one the switch below exists to make true, and states both directions of its
boundary (FR-035): what objecting stops, and the two things ingestion it does not stop.

### 4.3 Status and the switch

**`archiving`** (`Callout/success`):

- default: **Archival is on.** _New matches are picked up automatically._ Action: **Object to
  archival** (`Button/secondary`).
- `justResumed`: **Archival resumed.** _Future matches are captured again. Matches from while you
  had objected are not recovered — see above._ Action: **Object to archival** (`Button/secondary`).

**`objected`** (`Callout/info`): **Archival is off. You objected {objectedAt}.** _Your match
history and ratings still update. Nothing new is being downloaded or stored from your replays._
Action: **Resume archival** (`Button/primary`).

The objected callout is a calm statement of fact with a one-click way back, exactly as the
`declined` state was before this rebuild — not a warning, not the danger tone, no repeat of the
consequence paragraph in a larger size. FR-035 gives a user a right they may exercise while still
using the rest of the product; a red banner nagging on the dashboard afterwards would turn that
right into a penalty.

### 4.4 Failure copy

`WriteFailedRegion` (`Callout/danger`): heading **We could not save that choice**, body _Your choice
was not recorded, so nothing has changed. Try again when you are ready._ Direction-agnostic on
purpose: this copy is correct whether the failed write was an objection or a resumption, and it
never claims which state is now current — the caller does that by simply not changing `state`.

`unavailable` (`Callout/info`, both when the route cannot be reached at all): heading **We can't
save your choice right now**, body _Nothing has changed while this is unavailable._

## 5. States

**default** — as anatomised, `state` reflects the last-known server truth, the switch enabled.

**hover / focus-visible / active** — owned by `Button` and by the privacy link. The section itself
is not interactive and shows no hover affordance of its own. What each of those three states looks
like on the privacy link is §5.1 below: the `Link` primitive at `variant="standalone"`, in the
`link` ink.

**disabled** — the one visible switch button disables while its write is in flight, or while
`unavailable`. There is exactly one button rendered at a time (`state` picks which), so there is no
"one disabled, one not" case to rule out the way the old two-button decision row needed to.

**loading** — before `/api/me` resolves, `StatusRegion` renders as `Skeleton` blocks at the loaded
footprint (a text line for the heading, a block for the button). **The identity statement and the
basis statement never render as a skeleton** — both are static copy, available at first paint,
independent of whether the caller yet knows `state`.

**error** — `writeFailed`: `WriteFailedRegion` renders per §4.4, the switch returns to enabled, and
`state` is exactly what it was before the attempted write. The UI **must not** display the attempted
action as if it had taken effect — an optimistic archival state is one that was never actually
recorded, and this is the one place in the product where optimistic UI is forbidden outright,
carried over unchanged from the rule this replaced.

**empty** — this component has no list and no collection to be empty. Its only content is the
current archival status, which `state` always answers with one of exactly two values — there is no
third "nothing yet" fact for an empty state to represent. (Whether a linked profile has any archived
replays yet is `ProfileSummary`'s empty state, `profile-summary.md`'s own §5 — a fact about the
archive's contents, not about whether archiving is running.)

**selection** — not applicable. `state` is a fact about the account, not a choice among visible
items; there is no set for one member to be marked current within.

**expansion** — not applicable, and by rule rather than oversight: §4.1 bans placing any of the four
identity statements "behind a disclosure, a tooltip, a `title` attribute, a scroll-to-reveal or a
'Learn more'." Nothing in this component collapses.

### 5.1 `PrivacyNoticeLink`'s treatment — decided 2026-09-21 (T596)

**`PrivacyNoticeLink` is the `Link` primitive at `variant="standalone"`**
([`structural-tier.md`](./structural-tier.md) §9), not a local `<a>` and not a copy of any link
recipe. This subsection is that decision's only home; nothing in it is to be re-derived at
implementation time. Rendered literally:

```tsx
{
  privacyNoticeHref && (
    <Link href={privacyNoticeHref} variant="standalone">
      Read the privacy notice
    </Link>
  )
}
```

No `className`, no `external`, no other prop, and no state class of this component's own on or
around it. The wrapper it sits in carries the `space-4` gap of §7 and nothing else — no `text-sm`,
no `font-sans`, because `standalone` owns its own typography (`type-body` at `text-md`).

Its states are therefore `Link` `standalone`'s, as §9 defines them, with no local addition:

| State          | What the frame shows                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| default        | ink `link`, permanent underline at `border.hairline`                                                    |
| hover          | ink `link-hover`, underline thickened to `border.ring` — two signals, one not colour                    |
| focus-visible  | the `focus-ring` outline at `border.ring-offset` around the whole link box, over the hover paint        |
| active (press) | the hover paint, a `surface-sunken` fill behind the box, and a `border-strong` ring flush with its edge |
| disabled       | never. A link is never disabled (§9); `unavailable` disables the switch and not this link.              |

**Why the primitive rather than a local anchor with state classes added.** The copy is how this
defect happened: the shipped anchor renders `text-text-secondary underline` and paints no `hover:`,
`focus-visible:` or `active:` class of any kind, so no story could ever depict a state it does not
have. `Footer` reached the same conclusion for this same label under T591 — "rendering the primitive
directly instead of copying its recipe … with no second copy to drift out of sync again"
(`packages/design-system/src/composites/Footer/index.tsx`'s own note) — and FR-038 wants the two
"Read the privacy notice" links in this product to be one control rather than two that merely
resemble each other. A local recipe here would be one more copy of `Link`'s paint in the screens
tier, on top of the copies T591 already had to repair in lockstep when every one of them had lost
the same half of the same signal; the register records what happens to those, one signal at a time.

**Why `standalone` rather than `inline`.** §2 lists `PrivacyNoticeLink` as a top-level part, a
sibling of `StatusRegion` — not a run of words inside a sentence. §9's variant table calls that "a
navigation or action link on its own line", which is `standalone`; `inline`'s row is "a link inside
running prose", which this is not. Two consequences settle it beyond the taxonomy:

- **Touch target.** `standalone` reaches 44px by its own block padding (§9 Spacing), never by an
  overlay. The shipped `text-sm` anchor with no padding does not, and this file's own §9 states the
  44px floor — so `inline` would leave an accessibility criterion failing on purpose. The WCAG 2.5.8
  inline exception that excuses a link inside a running sentence does not reach this one, because
  this one is not inside a sentence.
- **A press signal a screenshot can resolve.** `inline`'s press is the underline dropping by one
  offset step, and that exact signal has already failed once in this package at this scale: it is
  what `Footer`'s hand-rolled link carried until T591, recorded there as "too weak for the duplicate
  check to tell apart from hover at this row's size". This screen's frames are larger than that row.
  `standalone`'s fill-plus-ring press is legible at that scale, and stays legible in the clipped
  capture its story takes.

**The `text-secondary` ink does not survive. This link renders in `link`**, like every other link in
the product. Three reasons, in the order that decides it:

1. **The primitive forbids caller-side ink by construction**, and that is the rule rather than an
   obstacle: `LinkProps` omits `className` precisely so "a caller never colours a link by hand"
   (`packages/design-system/src/primitives/Link/index.tsx`, quoting
   `contracts/005-design-system-foundations/structural-tier.md`). Keeping the muted ink would need
   either a `className` escape or a third `Link` variant, and FR-031 rejects a variant that exists
   to accommodate one call site.
2. **A de-emphasised route to the disclosure is a dark pattern in the one place this product cannot
   afford one.** FR-041 puts this link on the screen that carries the objection switch. Painting the
   only route to the full notice quieter than the prose around it is the shape consent-washing takes,
   and constitution IX's standing right to object is exercised by people who can first read what
   they are objecting to. In this file `text-secondary` is the timestamp colour: the shipped link
   reads as metadata about the page rather than as the way out of it.
3. **`link` is the ink whose pairs are validated for link text.** The README contrast table measures
   `link`/`link-hover`/`link-visited` on all four surfaces in both themes — referenced, not restated
   here — including `surface-sunken`, which is exactly what `standalone`'s own press fill paints
   behind this text. `text-secondary` is measured as body-adjacent text and never as a link over
   that fill.

**What this changes in the generated coverage region**, so the implementer is not surprised by it:
this anchor stops being a locally styled element of `screens/ArchivalControl` and becomes a `Link`
instance at `standalone`, which the extractor tracks on the primitive's own variant axis instead.
The three cells keyed to the local element go away with the element; whether the new stories also
credit `Link`'s own `standalone` rows is the extractor's answer to give and is not claimed here.

**What the commit that applies this owes** — T596's own instruction, together with the
`state-coverage-debt` entry in row 8 of [`README.md`](./README.md)'s contrast-signal register that
names the same three cells: one `Hover`, one `FocusVisible` and one `Active` story, each forcing its
state on `role: 'link'` named "Read the privacy notice" and each `visualCaptureClip`ped to that link
(the standing rule for a signal smaller than roughly 1% of its own frame);
`ArchivalControl.stories.tsx`'s `HoverFocusActiveNotApplicable` reworded so its rendered text no
longer claims these three states belong to another component; and the two transitional sentences in
§5 above, plus that register entry, deleted in the same commit.

## 6. Tokens used

Colour: `surface` (section), `surface-raised` (identity statement block and callouts), `border`
(block boundary), `text-primary` (heading, all four identity statements, basis paragraphs, callout
bodies), `text-secondary` (timestamps), `link` / `link-hover` / `link-visited` and `surface-sunken`

- `border-strong` (`PrivacyNoticeLink`, via `Link` `standalone` — §5.1; the muted ink it paints
  today is retired by that decision and is not to be reintroduced by a caller), `accent` family via
  `Button`, `danger` (error callout), `success` (archiving callout), `info` (objected callout,
  unavailable callout), `focus-ring`.
  `overlay` and `modal` elevation are no longer used by this component — carried by `Dialog`'s one
  remaining consumer, profile unlink, and nowhere in this file.

Typography: family `sans` throughout, `display` for the section heading only. Sizes — section
heading `xl`; `StatementHeading` and `BasisHeading` `md`; the four identity statements `md`; basis
paragraphs `md`; timestamps `xs`; `PrivacyNoticeLink` `md`, `Link` `standalone`'s own `type-body`
size rather than the `sm` the local anchor sets today. Weights — `semibold` on headings, `medium`
on the four identity statements, `normal` elsewhere. The identity statements are one weight step
above the surrounding prose: that is the only emphasis they get, and it is enough.

Radius `lg` (identity block, callouts), `md` (buttons), `control` (`PrivacyNoticeLink`'s own box,
`Link` `standalone`'s, visible where its press fill is).
Elevation `none` throughout — both text blocks are passages of text, not floating cards, and the
callout carries no extra elevation beyond its own default.
Motion: `duration.fast` + `easing.standard` on the switch button and on `PrivacyNoticeLink`'s colour
transition; `duration.normal` + `easing.decelerate` for the failure callout appearing;
`duration.instant` under `prefers-reduced-motion`. **No entrance animation on the identity
statement**: text that fades in can be answered before it is read.

Gaps in play: **DS-4** (focus ring), **DS-6** (reading measure — this block is long-form prose and
needs one).

## 7. Spacing

| Between                               | Step                                                                                                                                                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Section padding                       | `space-6` below `md`, `space-8` from `md`                                                                                                                                                                                       |
| Section heading to identity statement | `space-6`                                                                                                                                                                                                                       |
| Statement heading to first statement  | `space-3`                                                                                                                                                                                                                       |
| Between the four statements           | `space-3`                                                                                                                                                                                                                       |
| Fourth statement to rationale line    | `space-4`                                                                                                                                                                                                                       |
| Identity block padding                | `space-5`                                                                                                                                                                                                                       |
| Identity block to basis statement     | `space-8` — the widest gap in the composition, because these are two different subjects and the reader must feel the change                                                                                                     |
| Basis heading to first paragraph      | `space-3`                                                                                                                                                                                                                       |
| Between basis paragraphs              | `space-3`                                                                                                                                                                                                                       |
| Basis statement to status region      | `space-8`                                                                                                                                                                                                                       |
| Status region to privacy link         | `space-4`, measured to `PrivacyNoticeLink`'s own padded box and not to its text — `Link` `standalone`'s block padding is what carries the 44px target (§5.1), so the visible gap above the words is that padding plus this step |
| Write-failed callout above/below      | `space-6`                                                                                                                                                                                                                       |

## 8. Responsive

- **375** — one column. The switch button full width. The identity statement stays at font-size `md`
  and is **not** collapsed, truncated or moved below the basis statement to shorten the page. The
  page is allowed to be long. What is not allowed is `StatusRegion` being reachable without the
  identity statement having been on screen — accordingly `StatusRegion` is placed after both text
  blocks in DOM and visual order at every viewport, so it cannot be reached by scrolling past
  nothing. `PrivacyNoticeLink` sits on its own line under the status region at every width and is
  never pulled up beside the switch: a link that shares a line with the one decision control reads
  as its second option.
- **768** — text column capped at a 60–75 character measure (gap DS-6), left-aligned. The switch
  button intrinsic width, left-aligned with the text.
- **1280** — same as 768. The column does not widen. A single-column composition on a wide screen is
  correct here; do not invent a second column to balance it, and above all do not move the identity
  statement into a sidebar, where it becomes furniture.

## 9. Accessibility

- The block is a `<section aria-labelledby>` with an `<h2>`; `StatementHeading` and `BasisHeading`
  are `<h3>`. The four identity statements are a `<ul>` — they are a list of facts, and a screen
  reader announcing "list, four items" is accurate and useful.
- The whole block is inline page content, never a dialog: no `role="dialog"`, no focus trap, no
  Escape handler. The user can move around the page, read the privacy notice, and come back. This is
  unchanged from before, and is now true of the switch as well as of the surrounding text — there is
  no dialog anywhere left in this component.
- The switch is one `<button>`, never a checkbox and never a two-button row: one press, one action,
  no chance of a stale "which one did I press" ambiguity. Not `autofocus`.
- `PrivacyNoticeLink` is a real `<a href>` whose accessible name is its visible text and says where
  it goes (`Link`'s own rule, `structural-tier.md` §9, FR-051): "Read the privacy notice", never
  "here" and never the raw route. It is in the tab order after the switch, in DOM order.
- Reading order equals visual order equals DOM order: heading, identity statement, basis statement,
  status region, privacy link. Verified with CSS disabled.
- `StatusRegion`: `role="status"` for `archiving` and `objected` (via `Callout`'s own tone-to-role
  mapping), `role="alert"` for the write-failed callout. On a client-side action the region
  announces; focus does not move, because the user's hands are on the button they just pressed.
- Touch target ≥ 44px: the switch button renders at a size that clears 44px in every state, and so
  does `PrivacyNoticeLink` once §5.1 is applied, by `Link` `standalone`'s own block padding and
  never by an overlay. This is the floor the shipped `text-sm` anchor fails, and the second reason
  the variant is `standalone`.
- Contrast per the README table. The four identity statements are `text-primary` on
  `surface-raised`, the strongest pair available in both themes; that is deliberate and unchanged.
  `PrivacyNoticeLink` is `link` on `surface` at rest and `link` on `surface-sunken` while pressed —
  both measured rows of that table, both themes, referenced and not restated here.
- Zoom to 200% and 320px logical width without horizontal scrolling, with the identity statement
  fully readable.
- **Loading (T532, FR-054)**: the status region's own wrapper carries `aria-busy="true"` while it
  holds the two loading `Skeleton`s — one announcement for that region, never once per `Skeleton`
  (each stays `aria-hidden`, its own contract). See `shared-primitives.md`'s `StatValue` section for
  the general rule this follows.

## 10. Visual acceptance criteria

**Identity statement — the ones that matter most, unchanged by this amendment**

- [ ] All four statements are visible in the default screenshot without any click, hover, scroll
      inside a sub-container, or expansion.
- [ ] The four statements render in the primary text colour, at the same font size as the basis
      statement or larger, at one weight step above surrounding prose.
- [ ] The statements appear **above** `StatusRegion` in the frame at 375, 768 and 1280.
- [ ] The words "password reset", "email verification" and "recovery" each appear, negated.
- [ ] No shield, lock or tick icon appears anywhere in the identity block.
- [ ] No reassurance phrase from the banned list in §4.1 appears in the frame.
- [ ] The rationale line, if present, is the last line of the identity block and never the first.

**The switch**

- [ ] Exactly one decision control is rendered in any given screenshot, a real `<button>`, at least
      44px tall.
- [ ] No checkbox, no toggle switch styled to look optional, no control implying archival is
      currently undecided.
- [ ] `archiving`'s frame never shows an "objected" callout or vice versa — the two are mutually
      exclusive in a single render.
- [ ] Nothing in the default frame reads as a question awaiting an answer: no "Accept"/"Decline"
      pair, no unanswered/pending tone, anywhere.

**`PrivacyNoticeLink` (§5.1)**

- [ ] In the default frame the link is underlined and reads in the link ink — the same ink as the
      links in `Footer` and in the privacy notice, **not** the muted colour the timestamps use. A
      frame in which this link is the quietest text on the screen fails this criterion.
- [ ] Greyscale the default frame: the link is still identifiable as a link, by its underline alone.
- [ ] The link's box measures at least 44px tall at 375, measured from the rendered box and not from
      the glyph.
- [ ] The hover capture differs from the default capture in two ways: the ink is different and the
      underline is visibly thicker.
- [ ] The focus capture shows a ring around the whole link box, offset from the text, unclipped, in
      both themes, with the underline still visible under it.
- [ ] The press capture shows a filled, ringed box behind and around the link — overlay it on the
      hover capture and the fill and the ring are the difference, not the ink alone (FR-037).
- [ ] The link sits on its own line below the status region in every frame at 375, 768 and 1280, and
      never shares a line with the switch.

**States**

- [ ] Loading: `StatusRegion` shows skeleton blocks at the loaded footprint; the identity and basis
      statements render at full text, not skeletoned.
- [ ] Write failed: a danger callout is present, the switch is enabled again, and nothing in the
      frame claims the attempted action was saved.
- [ ] `objected`: the info tone, not danger; a single "Resume archival" button is present; there is
      no persistent red banner.
- [ ] `archiving`, `justResumed`: the success tone, with the "resumed" heading distinguishable in
      the frame from the plain "Archival is on." heading of the default `archiving` story.
- [ ] `unavailable`: the switch is disabled and `PrivacyNoticeLink` is not — a link is never
      disabled, and the route to the notice does not depend on the write route being reachable.

**Craft**

- [ ] Text column holds roughly 60–75 characters per line at 1280; it does not span the viewport.
- [ ] No game artwork, logo, portrait or in-game font in the frame.
- [ ] Focus ring visible and unclipped on the switch button in both themes. In the `archiving`
      state (`Button/secondary`), the ring is `focus-ring`, 2px outside the button's own edge, and
      clears 3:1 against the `Callout` behind it. In the `objected` state (`Button/primary`, "Resume
      archival"), the ring is the inward `accent-contrast` ring instead (DS-10, `color-tokens.md`
      §5) — a band of `accent` fill separates it from the button's own edge on every side
      (`-outline-offset-4`, T586), so it reads against that fill (6.07:1 light / 8.07:1 dark), never
      against `Callout/info`'s `bg-surface-raised` fill behind it, which the ring never touches.
- [ ] The identity block and the basis statement carry no shadow and read as passages of text, not
      as cards competing with `StatusRegion` for attention.
- [ ] The section heading is visibly larger and heavier than `StatementHeading`/`BasisHeading`, which
      are in turn heavier than the prose beneath them — a token-correct frame that gave a subheading
      the section heading's own size would blur the two "what this block is about" cues into one,
      and fails this criterion (FR-063).
