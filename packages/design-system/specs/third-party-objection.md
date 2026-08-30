# ThirdPartyObjectionForm

**Component**: `src/components/ThirdPartyObjectionForm/`
**Feature**: 001, US5 — built by T095, composed by `apps/web/src/routes/object.tsx`, a route **outside
the session**, reachable from the privacy notice (`PrivacyNotice` §4.7's `ObjectionCallToAction`) and
from the footer (T098).
**Requirements**: FR-039 (a way for a non-user in archived matches to object, and pseudonymisation of
their identifiers on request without corrupting match records). FR-038 (non-users are never publicly
exposed or indexed — this screen holds no listing of anyone). Constitution IX and X.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`. This component
defines its own labelled numeric field inline, exactly as `SearchBox`
([`player-search.md`](./player-search.md) §2) defines its own input — there is no shared form-field
primitive, and inventing a general one for the two fields the product has is out of scope here.
**Sources of truth this behaviour and copy are derived from, and must not contradict**:
`apps/api/src/aoe2stats_api/routers/privacy.py` — `POST /api/privacy/object`: **unauthenticated by
design**, takes `{"profile_id": int}`, is rate limited (429 with `retry_after`), **records** one
`data_requests` row and **pseudonymises nothing on the call** (a person resolves it later, within the
delay `docs/privacy/processing-register.md` names); and [`privacy-notice.md`](./privacy-notice.md)
§4.7, the normative home of the non-user disclosure this screen states at the point of action.

**This is the one screen in the product addressed to someone who is not a user and has no session.**
Two consequences shape everything below. First, it must be **self-contained**: no signed-in chrome, no
"your profile" header, nothing that assumes an account, and no fetch that requires a cookie — the whole
page renders and works with no session at all, because its entire audience has none. Second, and this
is FR-039's ordering requirement made into anatomy: it **explains what is held about the reader and
why before it asks them for anything**. The form is below the explanation, never above it and never
beside it; a person must be able to understand what they are objecting to before the field that
collects the objection is in reach.

**It records, it does not act, and the copy must not overstate.** The endpoint writes a request for a
human to resolve; it does not pseudonymise on submit. The success wording therefore says the objection
was **recorded** and that a person will act within the stated delay — never that the data has already
been changed. This is the safeguard the processing register's balancing test cites for processing
third parties, so the copy carrying it is load-bearing.

## 1. Purpose

Let a person who never signed in — who appears here only because they played a match against someone
who did — understand what this service holds about them and on what basis, and lodge an objection that
a human will act on, without needing an account, an email address or a password they were never asked
for.

## 2. Anatomy

```
ThirdPartyObjectionForm                     <main> with a single <h1>; no auth chrome
├─ Heading                    h1 — "Object to what is held about you"
├─ Explanation                the disclosure, always above the form (§4.2)
│  ├─ WhoThisIsFor            you appear here without ever signing in — why
│  ├─ WhatWeHold             the public match fields + in-recording actions/chat
│  ├─ WhyWeHold              legitimate interest (Art. 6-1-f), stated as basis not reassurance
│  ├─ WhatObjectingDoesAndDoesNot   recorded, human resolves within the delay, pseudonymised not deleted
│  └─ PrivacyNoticeLink       inline link to the full notice — accent on surface (DS-9)
├─ ObjectionForm              <form>
│  ├─ Field
│  │  ├─ Label                "Your Age of Empires II profile id" — visibly tied to Input
│  │  ├─ Input                inputmode="numeric", one field, the only thing asked for
│  │  ├─ HelpText            text-secondary — what a profile id is and where it is visible
│  │  └─ FieldError ×0..1     the value is missing or not a number
│  └─ SubmitButton            Button/primary — "Record my objection"
├─ FormFailure     ×0..1      Callout/warning (rate limited) or Callout/danger (request failed)
└─ (on success) → RecordedConfirmation replaces the form, keeping the explanation (§4.4)
```

**One field, and it is the only thing asked for** — `PrivacyNotice` §4.7 fixes this: "no account, no
sign-in, no email address, because we have no way to ask you for one and no way to answer you." The
form must not grow a name field, a contact field or a message box; there is no channel to reply on, so
collecting a reply address would be collecting data we cannot use, from the exact people this screen
exists to collect less about.

**This screen lists nobody (FR-038).** It has no search, no "is this you?" preview, no profile lookup
that would render a person's alias back to them. It takes a profile id the reader already has and
records an objection against it; it never turns that id into a displayed profile, because doing so
would publicly expose the non-user this feature exists to protect.

**Known friction, flagged for T095 and the reviewer, not solved here.** A non-user must supply their
numeric `profile_id`, which the API is keyed on (router) — the form cannot offer a name search, since
that is a session-bound feature and would itself list people (FR-038). `HelpText` (§4.2) says where the
id is visible. If product later wants a gentler path in, that is a new decision with its own spec; this
component stays faithful to the one input the endpoint accepts rather than inventing a lookup it has no
endpoint for.

## 3. Variants, sizes and props

One instance, no variant axis, one size. Full width of the page's text column at every viewport (§8).

```ts
interface ThirdPartyObjectionFormProps {
  /** POST /api/privacy/object. Resolves on 202; rejects with a typed reason otherwise. */
  onSubmit: (profileId: number) => Promise<void>
  /** Full privacy notice route, for the inline link in the explanation. Required. */
  privacyNoticeHref: string
  /** Injected only by stories to render a fixed state; the route never sets it. */
  initialState?: ObjectionUiState
}

type ObjectionUiState =
  | 'idle' // explanation + empty field
  | 'submitting' // POST in flight
  | 'recorded' // 202; RecordedConfirmation shown
  | 'rate-limited' // 429; FormFailure/warning, with the retry hint
  | 'failed' // network or 5xx; FormFailure/danger, retryable
```

`privacyNoticeHref` is **required**, not optional: a disclosure screen that cannot reach the fuller
notice is incomplete, and a build where FR-041's notice has no address should not compile rather than
render a dead reference — the same reasoning `privacy-notice.md` §5 gives for its required
`objectionForm` href, in the opposite direction.

## 4. Copy

Normative. The implementer copies these strings. This copy is the point-of-action twin of
[`privacy-notice.md`](./privacy-notice.md) §4.7 and must agree with it; a change to what objecting does
happens in both, in one PR, with the notice/register chain in `privacy-notice.md`'s header governing
order.

**Banned throughout, each checkable in review:**

- Any claim the data has already been changed on submit: "your data has been removed", "you have been
  anonymised", "done". It is **recorded**; a person acts later. Saying otherwise is a false statement
  about a legal act.
- "Anonymous", "anonymised", "anonymisation". The act is **pseudonymisation**, re-identifiable by
  design (constitution IX). Wrong word, wrong legal claim.
- Reassurance in place of fact: "we take your privacy seriously", "rest assured", "we've got you
  covered".
- A promise of a reply this system cannot make: "we'll email you", "we'll be in touch", "check your
  inbox", "we'll confirm by email". There is no channel back to a non-user, and the form says so
  rather than implying one.
- A shield, lock, tick or padlock icon anywhere in the component.

### 4.1 Heading

`Heading` (`h1`): **Object to what is held about you**

### 4.2 Explanation — always above the form (FR-039 ordering)

`WhoThisIsFor`:

> You can appear in this service without ever having signed in to it. You played a match against
> someone who uses it, and Age of Empires II publishes that match. This page is for you, and it does
> not need an account.

`WhatWeHold`:

> What we hold about you is the public part of that match — your profile id, alias, country,
> civilisation, team, colour, result, rating and rating change, all of it already published by the
> game on its own leaderboards. Inside the recording that other player's own game produced, your
> in-game actions and whatever was typed in chat are in the file too, because a recording cannot be
> split apart per player. We never capture your own point of view of a match.

`WhyWeHold`:

> We hold it on the basis of our legitimate interest in saving these matches before the game deletes
> them (GDPR Art. 6-1-f), not on your consent. This form is how you object to that.

`WhatObjectingDoesAndDoesNot`:

> When you object, we record it with the date. A person reads it and acts within 30 days, replacing
> your profile id in our match records with a pseudonymous one, so what remains no longer names you.
>
> Objecting does not delete the matches, which are other players' records too, and it does not delete
> or alter a recording. This is pseudonymisation, not anonymisation — the record still describes a
> game somebody played. To read the whole of what is held and why, see the {privacy notice}.

`PrivacyNoticeLink`: the phrase **privacy notice** in the last sentence links to `privacyNoticeHref`
(`accent`, permanent underline, on `surface` — the DS-9-permitted pair).

### 4.3 The form

`Label`: **Your Age of Empires II profile id**

`HelpText` (`text-secondary`, below the input):

> This is the number Age of Empires II and its public leaderboards use to identify a player. It is the
> number in the address of a player's profile page. It is the only thing this form asks for.

`SubmitButton`: **Record my objection** (`Button/primary`). Loading label: **Recording your
objection…**

`FieldError` (missing or non-numeric): **Enter your numeric profile id — just the number.**

### 4.4 Outcomes

`RecordedConfirmation` (replaces the form; the explanation above it stays):

> **Your objection has been recorded.** _A person will act on it within 30 days, replacing your profile
> id in our match records with a pseudonymous one. Nothing has been changed yet, and there is no
> account here to sign in to — this is the whole of what happens, and we would rather say so than send
> a confirmation we have no address for._

`FormFailure`, rate limited (`Callout/warning`, the `POST`'s `429`): **Too many objections right now.**
_This form is busy. Please try again shortly._ — the retry hint uses the `retry_after` the endpoint
returns; the button returns to enabled once the window passes.

`FormFailure`, request failed (`Callout/danger`, network or `5xx`): **We could not record your
objection.** _Nothing was recorded. Try again when you are ready._ — with the button enabled again.

## 5. States

**default** — `idle`: heading, the full explanation, then the form with an empty field and the enabled
submit button. No failure callout, no confirmation.

**hover** — the privacy-notice link (`accent-hover`, underline stays) and the submit button (per
`Button`). No other part responds to a pointer.

**focus-visible** — the standard ring (`focus-ring`, `outline-2 outline-offset-2`, gap DS-4) on the
input, the submit button and the privacy-notice link, in both themes. The input additionally shows a
focus boundary distinct from its resting boundary so a keyboard user sees where they are.

**active** — the link renders `accent-active` while pressed; the button per `Button`. Nothing scales.

**disabled** — **the submit button is never disabled.** Validation happens on submit, not by greying
the button, so a non-user is never faced with a dead control and no explanation of why. Pressing submit
with an empty or non-numeric field shows `FieldError` and moves focus to the field; it does not
silently do nothing. (Rationale: a disabled submit on a form a stranger meets once is a dead end with
no affordance to recover from — the opposite of what an objection route owes the person it is for.)

**loading** — `submitting`: the submit button shows its loading label and busy state; the field is
`readonly` for the duration so the value cannot change under an in-flight request. There is **no
page-load skeleton** — this screen fetches nothing to render, holds no session, and must be fully
readable at first paint, exactly like `PrivacyNotice`.

**error** — three, all distinct and all recoverable: `FieldError` inline for a bad value;
`FormFailure/warning` for `rate-limited` (429), naming the retry; `FormFailure/danger` for `failed`, on
which nothing was recorded and the button is enabled again. None of the three ever claims a partial
success.

**empty** — the resting `idle` field **is** the empty state, and it is a real rendered state: the
explanation is always present, the field carries its label and help text, and the button is live. There
is no collection here to be otherwise empty, and there is no state in which the explanation is absent —
a form that asks before it explains would violate FR-039's ordering.

## 6. Tokens used

Colour: `surface` (the page and all explanatory prose — the one background the inline link is measured
on), `surface-raised` (`FormFailure` and `RecordedConfirmation` `Callout` fills), `border` (the
input's resting boundary, section rules), `border-strong` (the input's boundary at the contrast floor
a control owes; `secondary` button boundary via `Button`), `text-primary` (heading, body, label,
confirmation body), `text-secondary` (`HelpText`, timestamps), `accent` family via `Button` and the
inline link, `warning` (rate-limited callout stripe/heading), `danger` (request-failed callout, and
`FieldError` text), `success` (`RecordedConfirmation` stripe/heading), `focus-ring`.

Typography: family `sans` throughout; `display` on the `h1` only. Sizes — `h1` `2xl` (dropping no lower
than `xl` below `md`); explanatory paragraphs and the confirmation body `md`; `Label` `md` weight
`semibold`; `HelpText` and `FieldError` `sm`; the input value `md`. Weights — `semibold` on the heading
and the label and the bolded lead phrases ("Your objection has been recorded.", "Too many objections
right now."), `normal` elsewhere. Tracking `normal`; nothing here is a compared numeral.

Radius `md` on the input and the submit button, `lg` on the callouts. Elevation `none` throughout — a
disclosure page is a document, not a stack of cards.

Motion: `duration.fast` + `easing.standard` on the link and button colour changes; `duration.normal` +
`easing.decelerate` for a `Callout` or the confirmation appearing; `duration.instant` under
`prefers-reduced-motion: reduce`. **No entrance animation on the explanation** — text a reader must
absorb before acting cannot fade in under them.

Gaps in play: **DS-4** (focus ring), **DS-5** (breakpoints), **DS-6** (reading measure), and **DS-9**:
the inline privacy-notice link sits on `surface` and only on `surface`, where `accent` with a permanent
underline is the measured pair (4.9 light / 7.7 dark). The `RecordedConfirmation` and `FormFailure`
callouts, on `surface-raised`, contain **no** inline link — anything the reader might follow from them
is stated in the on-`surface` prose instead, so no link is ever painted on a raised surface until DS-9
closes.

## 7. Spacing

| Between                                            | Step                                                                                      |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Page padding                                       | `space-6` below `md`, `space-8` from `md`                                                 |
| `h1` to the first explanation block                | `space-4`                                                                                 |
| Between explanation blocks                         | `space-4`                                                                                 |
| Explanation to `ObjectionForm`                     | `space-8` — the widest gap; the reader must feel the shift from being told to being asked |
| `Label` to `Input`                                 | `space-2`                                                                                 |
| `Input` to `HelpText`                              | `space-2`                                                                                 |
| `Input` to `FieldError`                            | `space-2`                                                                                 |
| `Field` to `SubmitButton`                          | `space-6`                                                                                 |
| Form to `FormFailure`                              | `space-6`                                                                                 |
| Explanation to `RecordedConfirmation` (on success) | `space-8`                                                                                 |

## 8. Responsive

- **375** — one column, full width less the page padding. The input and the submit button are full
  width; the button stacks below the field. No horizontal scrolling. The explanation is a plain,
  full-width column of paragraphs; nothing is truncated or put behind a "read more".
- **768** — text column capped at a 60–75 character measure (gap DS-6), left-aligned. The input holds a
  comfortable width within the measure (not stretched edge to edge); the submit button is intrinsic
  width, left-aligned under the field.
- **1280** — identical to 768; the measure does not widen and no second column, sidebar or hero panel
  appears. At every viewport the explanation renders in full and above the form — the ordering FR-039
  requires never becomes a layout casualty.

## 9. Accessibility

- Root is `<main>` with a single `<h1>`; the route renders no competing `<h1>`. The explanation
  paragraphs are ordinary prose; if grouped, the group heading is an `<h2>` and levels never skip.
- `ObjectionForm` is a `<form>`. `Input` is a real `<input inputmode="numeric">` with a programmatic
  `<label>` association (`for`/`id`), `HelpText` linked via `aria-describedby`, and — while a
  `FieldError` is present — `aria-invalid="true"` with the error also in `aria-describedby`. On a
  failed submit, focus moves to the input.
- `SubmitButton` is a real `<button type="submit">`. Submit works by Enter from the field and by
  activating the button. It is never a `<div>` with a handler.
- `FormFailure` announces via `Callout`'s `role="status"` (warning) or `role="alert"` (danger);
  `RecordedConfirmation` via `role="status"`. A callout present at first paint is never `aria-live`.
- The inline privacy-notice link is an `<a>` with a permanent underline, never colour alone (README
  rule 4).
- Touch targets: the input, the submit button and the link each clear 44px (the input via its own
  height, the link inside prose taking WCAG 2.5.8's inline exception where it runs inside a sentence).
- Contrast per the README table, both themes: body and label `text-primary` on `surface`; `HelpText`
  `text-secondary` on `surface`; the inline link `accent` on `surface`; the input boundary
  `border-strong` on `surface` (the 3:1 non-text floor a control owes); `FieldError` `danger` on
  `surface`; callout headings `warning` / `danger` / `success` on `surface-raised`, bodies
  `text-primary`.
- Reading order equals visual order equals DOM order, verified with CSS disabled: heading, explanation,
  then form — the explanation must precede the field in source, not only on screen.
- The whole screen works with **no session cookie and no JavaScript-loaded data**: it renders, reads
  and (with the form's own submit) functions for a visitor the rest of the app has never seen.
- Zoom to 200% and 320px logical width with no horizontal scrolling and no clipped field.

## 10. Visual acceptance criteria

**Order and self-containment — the point of the screen**

- [ ] In a full-page screenshot at 375, 768 and 1280, the explanation appears **above** the input
      field; the field is never above or beside the explanation.
- [ ] The page carries no signed-in chrome: no "your profile", no account menu, no avatar, nothing that
      assumes a session.
- [ ] There is exactly one input on the form, and it is the profile-id field; there is no name, email,
      message or contact field anywhere in the frame.
- [ ] No profile, alias or search result for any person is rendered — the screen lists nobody.

**The wording that is load-bearing**

- [ ] "legitimate interest" and "Art. 6-1-f" both appear in the explanation.
- [ ] "30 days" appears, describing when a person acts.
- [ ] "pseudonymisation" (or "pseudonymous") appears, and "anonymous" / "anonymised" appear **nowhere**
      in any frame.
- [ ] The `recorded` frame says the objection was **recorded** and that nothing has been changed yet;
      no frame claims the data has already been removed or anonymised.
- [ ] The `recorded` frame contains no promise of an email or a reply.

**States**

- [ ] `idle`: explanation, an empty field with its label and help text, and an enabled "Record my
      objection" button — the submit button is never rendered disabled in any frame.
- [ ] `submitting`: the button shows its loading label and busy state at the same width as at rest.
- [ ] Field error: the message is visible beside the field, the field is marked invalid, and no
      success or "recorded" wording is in the frame.
- [ ] `rate-limited`: a warning callout is present with a try-again message; the button is present.
- [ ] `failed`: a danger callout states nothing was recorded, and the button is enabled again.

**Tone, prohibitions and craft**

- [ ] No shield, lock, padlock or tick icon anywhere in any frame.
- [ ] At 375 there is no horizontal scrollbar and the field and button are full width.
- [ ] At 768 and 1280 the text column holds roughly 60–75 characters per line and does not span the
      viewport; the measure is the same at both.
- [ ] The focus ring is visible and unclipped on the input, on the submit button and on the inline
      privacy-notice link, in both themes.
- [ ] The inline link is underlined, not colour alone, and sits on `surface` (never inside a coloured
      callout).
- [ ] No game artwork, logo, portrait or in-game font in any frame.
