# ConsentStep

**Component**: `src/components/ConsentStep/`
**Feature**: 001, US1 and US5 — consumed by `apps/web/src/features/profile/` (T037) and the privacy
route
**Requirements**: FR-006 (the identity statement), FR-034, FR-035, FR-041. Constitution IX.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`.

## 1. Purpose

Ask the user, once and separately from creating their account, whether we may archive their replays
— after telling them plainly, and before they answer, that their Steam account is the only way in
and that there is no way back if they lose it.

## 2. Anatomy

```
ConsentStep
├─ Heading                    h2
├─ IdentityStatement          FR-006. Four statements + one rationale line. Always visible.
│  ├─ StatementHeading        h3
│  ├─ Statement ×4            each its own line, primary text colour
│  └─ RationaleLine           last, and only last
├─ ArchivalExplanation        what we would do, and why it is urgent
│  ├─ ExplanationHeading      h3
│  └─ Paragraph ×5
├─ DecisionRow                two buttons, equal size, equal reach
│  ├─ AcceptButton            Button/primary/lg
│  └─ DeclineButton           Button/secondary/lg
├─ ConsequenceLine            factual, below the decision, never above it
├─ WithdrawalLine             you can change this later, and what happens then (FR-035)
├─ PrivacyNoticeLink          FR-041
└─ StatusRegion               Callout ×0..1 — the write failed, or the decision is recorded
```

The `IdentityStatement` is the first block after the heading. It is not in an accordion, not in a
tooltip, not behind "Learn more", not below the fold on a phone, and not in a smaller or lighter
type than the archival explanation. FR-006 says "stated plainly before they consent to anything
being archived"; anatomy is how that becomes checkable.

## 3. Variants and sizes

| Variant            | When                                          | Shape                                                                                                                                                                                                                                                   |
| ------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `onboarding`       | first run, after linking, before any capture  | The full anatomy above. An inline section on the page, **not a modal**: a dialog the user cannot dismiss is a worse way to ask for consent than a page they can read at their own pace, and a dismissible dialog invites Escape as an accidental answer |
| `settings`         | managing an existing decision (privacy route) | Heading, current state, when it was recorded, one `Button` performing the opposite action, the withdrawal line, the privacy link. The `IdentityStatement` renders in its short form: `StatementHeading` plus statements 1 and 2                         |
| `withdraw-confirm` | the user is turning archival off              | A real dialog. Heading "Turn off replay archival?", the consequence line, "Turn it off" (`Button/destructive`) and "Keep it on" (`Button/secondary`). States what happens to already-archived replays                                                   |

One size. The block is a reading composition; it has no compact form. Shrinking it is how the
identity statement stops being read.

## 4. Copy

Normative. The implementer copies these strings; they are not placeholders. If product wants them
changed, the change happens in this file first.

### 4.1 Identity statement (FR-006)

`StatementHeading`: **Before you decide: how you get back in**

1. Your Steam account is the only key to this account. There is no password.
2. If you lose access to your Steam account, you lose access here. We cannot let you back in.
3. There is no password reset, no email verification and no account recovery — not through support,
   not by proving who you are, not by any other route.
4. Getting a Steam account back is between you and Valve. We are not part of that.

`RationaleLine`, last and never first: _We never store a password, so there is nothing here to
steal and nothing to reset. That is the trade._

**Banned in this block**, and each one is checkable in review:

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
- Placing the block after the decision row, or after the archival explanation.

### 4.2 Archival explanation

`ExplanationHeading`: **What we would archive**

1. Age of Empires II deletes your replay files about 31 days after the match. After that nobody can
   get them back — not you, not us, not Microsoft.
2. If you turn this on, we download the recording of each of your matches from your own point of
   view and keep the original file, unchanged.
3. We only ever take your own point of view, never another player's.
4. This runs by itself. You never have to remember to do anything.
5. It covers every Steam account you have linked, so no linked profile quietly expires.

### 4.3 Decision

- Accept: **Archive my replays**
- Decline: **Not now**

`ConsequenceLine`, `text-secondary`, size `sm`, directly below the decision row: _While this is off,
nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft's
servers, and the only copy left will be the one on your own machine, if you still have it._

`WithdrawalLine`, `text-secondary`, size `sm`: _You can change this whenever you like. Turning it
off stops future captures; replays already archived stay until you delete them, and you can export
or erase everything at any time._

### 4.4 Recorded states

- Accepted (`Callout/success`): **Archival is on.** _We started with the last 31 days. New matches
  are picked up automatically._
- Declined (`Callout/info`): **Archival is off.** _Your profile, ratings and match history still
  work. Nothing of yours is being downloaded or stored._ Action: **Turn on archival**.

The declined state is a calm statement of fact with a one-click way back. It is not a warning, it
does not use the danger tone, and it does not repeat the consequence line in a larger size. FR-034
requires a decision the user may decline while still using the rest; a decline that leaves a red
banner nagging on the dashboard is a refusal dressed as an acceptance.

## 5. States

**default** — as anatomised, no decision recorded, both buttons enabled.

**hover / focus-visible / active** — owned by `Button` and by the privacy link. The section itself
is not interactive and shows no hover affordance.

**disabled** — both buttons disable together while a decision is being written, never one at a time.
There is no state in which accepting is possible and declining is not. If consent cannot be recorded
at all (route unavailable), both are disabled and a `Callout/info` in `StatusRegion` says so and
says nothing is being archived meanwhile.

**loading** — the pressed button enters `Button`'s loading state ("Saving your choice…"); the other
becomes disabled but stays visible at the same size, so the layout does not shift and so the user
can still see what the alternative was. In the `settings` variant, before `/api/me` resolves, the
current-state line and its button are `Skeleton` blocks at the loaded footprint. **The identity
statement never renders as a skeleton** — it is static copy and it is available at first paint.

**error** — writing the decision failed. `Callout/danger` in `StatusRegion`: heading "We could not
save that choice", body "Your choice was not recorded, so nothing has changed. Nothing of yours is
being archived." Both buttons return to enabled. The UI **must not** display the attempted decision
as if it had taken effect — an optimistic consent is a consent that was never given, and this is the
one place in the product where optimistic UI is forbidden outright.

**empty** — two distinct emptinesses, and they must not look alike:

1. _No decision recorded yet_ (`settings` variant, an account created before this step ran): the
   current-state line reads "You have not answered this yet." in `text-primary`, and the full
   `onboarding` decision row renders below it. Never render an unanswered consent as "off": those
   are different facts, and only one of them is a decision.
2. _Consent recorded, nothing archived yet_: the accepted callout's secondary line reads "Nothing
   has been archived yet. The first sweep runs within a day." Never an empty list with a spinner.

## 6. Tokens used

Colour: `surface` (section), `surface-raised` (identity statement block and callouts),
`surface-sunken` (disabled controls), `border` (block boundary), `text-primary` (heading, all four
statements, explanation paragraphs, callout bodies), `text-secondary` (consequence line, withdrawal
line, timestamps), `accent` family via `Button`, `danger` (error callout, destructive confirm),
`success` (accepted callout), `info` (declined callout), `focus-ring`, `overlay` (the
`withdraw-confirm` dialog backdrop only).

Typography: family `sans` throughout, `display` for the section heading only. Sizes — section
heading `xl`; `StatementHeading` and `ExplanationHeading` `md`; the four statements `md`;
explanation paragraphs `md`; consequence and withdrawal lines `sm`; timestamps `xs`. Weights —
`semibold` on headings, `medium` on the four statements, `normal` elsewhere. The statements are one
weight step above the surrounding prose: that is the only emphasis they get, and it is enough.

Radius `lg` (identity block, callouts), `md` (buttons), `xl` (`withdraw-confirm` dialog).
Elevation `none` on the identity block — it is a passage of text, not a floating card — `raised`
on nothing here, `modal` on the `withdraw-confirm` dialog only.
Motion: `duration.fast` + `easing.standard` on buttons; `duration.normal` + `easing.decelerate` for
the status callout appearing; `duration.instant` under `prefers-reduced-motion`. **No entrance
animation on the identity statement**: text that fades in can be answered before it is read.

Gaps in play: **DS-4** (focus ring), **DS-6** (reading measure — this block is long-form prose and
needs one).

## 7. Spacing

| Between                                     | Step                                                                                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Section padding                             | `space-6` below `md`, `space-8` from `md`                                                                                   |
| Section heading to identity statement       | `space-6`                                                                                                                   |
| Statement heading to first statement        | `space-3`                                                                                                                   |
| Between the four statements                 | `space-3`                                                                                                                   |
| Fourth statement to rationale line          | `space-4`                                                                                                                   |
| Identity block padding                      | `space-5`                                                                                                                   |
| Identity block to archival explanation      | `space-8` — the widest gap in the composition, because these are two different subjects and the reader must feel the change |
| Explanation heading to first paragraph      | `space-3`                                                                                                                   |
| Between explanation paragraphs              | `space-3`                                                                                                                   |
| Explanation to decision row                 | `space-8`                                                                                                                   |
| Between the two decision buttons            | `space-3`                                                                                                                   |
| Decision row to consequence line            | `space-4`                                                                                                                   |
| Consequence line to withdrawal line         | `space-2`                                                                                                                   |
| Withdrawal line to privacy link             | `space-4`                                                                                                                   |
| Status callout above/below the decision row | `space-6`                                                                                                                   |

## 8. Responsive

- **375** — one column. Buttons full width, stacked at `space-3`, accept first. The identity
  statement stays at font-size `md` and is **not** collapsed, truncated or moved below the archival
  explanation to shorten the page. The page is allowed to be long; consent is allowed to take
  scrolling. What is not allowed is the decision row being reachable without the identity statement
  having been on screen — accordingly the decision row is placed after both text blocks in DOM and
  visual order at every viewport, so it cannot be reached by scrolling past nothing.
- **768** — text column capped at a 60–75 character measure (gap DS-6), left-aligned. Buttons
  intrinsic width, side by side, left-aligned with the text.
- **1280** — same as 768. The column does not widen. A single-column composition on a wide screen is
  correct here; do not invent a second column to balance it, and above all do not move the identity
  statement into a sidebar, where it becomes furniture.

`withdraw-confirm` is a bottom sheet below `md` and a centred dialog from `md` up.

## 9. Accessibility

- The block is a `<section aria-labelledby>` with an `<h2>`; `StatementHeading` and
  `ExplanationHeading` are `<h3>`. The four statements are a `<ul>` — they are a list of facts, and
  a screen reader announcing "list, four items" is accurate and useful.
- `onboarding` is **not** a dialog: no `role="dialog"`, no focus trap, no Escape handler. The user
  can move around the page, read the privacy notice, and come back.
- The decision buttons are two `<button>` elements, not a radio group with a submit: one press, one
  decision, no chance of submitting an unselected form. Neither is `autofocus`.
- Reading order equals visual order equals DOM order: heading, identity statement, archival
  explanation, decision. Verified with CSS disabled.
- `StatusRegion`: `role="status"` for success and info, `role="alert"` for the error. On a
  client-side decision the region announces; focus does not move, because the user's hands are on
  the button they just pressed.
- `withdraw-confirm`: `role="dialog"` with `aria-modal="true"`, focus moved to the dialog heading on
  open, focus trapped while open, Escape closes and cancels (Escape must never be the path that
  turns archival off), focus returned to the trigger on close.
- Touch targets ≥ 44px: both decision buttons render at `lg` (48px) and are the same height as each
  other at every viewport. A decline control that is smaller, lighter, textual or lower-contrast
  than the accept control is a dark pattern and fails this spec regardless of how it looks.
- Contrast per the README table. The four statements are `text-primary` on `surface-raised`, the
  strongest pair available in both themes; that is deliberate.
- Zoom to 200% and 320px logical width without horizontal scrolling, with the identity statement
  fully readable.

## 10. Visual acceptance criteria

**Identity statement — the ones that matter most**

- [ ] All four statements are visible in the default screenshot without any click, hover, scroll
      inside a sub-container, or expansion.
- [ ] The four statements render in the primary text colour, at the same font size as the archival
      explanation or larger, at one weight step above surrounding prose.
- [ ] The statements appear **above** the decision buttons in the frame at 375, 768 and 1280.
- [ ] The words "password reset", "email verification" and "recovery" each appear, negated.
- [ ] No shield, lock or tick icon appears anywhere in the identity block.
- [ ] No reassurance phrase from the banned list in §4.1 appears in the frame.
- [ ] The rationale line, if present, is the last line of the block and never the first.

**Decision row**

- [ ] Exactly two decision controls, both real buttons, both at least 44px tall, of equal height.
- [ ] The decline control is a labelled button reading "Not now" — not a text link, not an ✕, not
      "skip", not smaller than the accept control.
- [ ] No checkbox is pre-ticked; no consent is implied by continuing.
- [ ] The consequence line sits below the decision row, in the secondary text colour, at size `sm`,
      and does not use the danger tone.

**States**

- [ ] Loading: the pressed button shows a spinner and its participle label; the other button is
      visibly disabled but unchanged in size; the layout has not shifted.
- [ ] Error: a danger callout is present, both buttons are enabled again, and nothing in the frame
      claims the choice was saved.
- [ ] Declined (`settings`): the info tone, not danger; a single "Turn on archival" button is
      present; there is no persistent red banner.
- [ ] Unanswered (`settings`): reads "You have not answered this yet", not "off".

**Craft**

- [ ] Text column holds roughly 60–75 characters per line at 1280; it does not span the viewport.
- [ ] No game artwork, logo, portrait or in-game font in the frame.
- [ ] Focus ring visible and unclipped on each decision button in both themes.
- [ ] The identity block carries no shadow and reads as a passage of text, not as a card competing
      with the decision row for attention.
