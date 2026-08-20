# SignInScreen

**Component**: `src/components/SignInScreen/`
**Feature**: 001, US1 — consumed by `apps/web/src/routes/sign-in.tsx` (T036)
**Requirements**: FR-001, FR-002, FR-003, FR-005, FR-006, FR-007. SC-004.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`.

## 1. Purpose

Let a visitor prove they own a Steam account and reach their own Age of Empires II figures without
typing an identifier — and, when that does not work, tell them exactly why and give them the way
forward instead of an empty dashboard.

## 2. Anatomy

```
SignInScreen
├─ Frame                  centred panel on the page background
│  ├─ Brandmark           original abstract mark (see IP note)
│  ├─ Title               h1
│  ├─ Value line          why this exists, one sentence
│  ├─ OutcomeRegion       Callout ×0..1 — the three failures and the transport failure
│  ├─ ActionRow           the Steam button (Button/primary/lg) + secondary action when the
│  │                      outcome calls for one
│  ├─ NoAdminLine         "No identifier to type…"
│  ├─ IdentityNote        the short form of FR-006, always present, never behind a disclosure
│  └─ BetaNote            closed-beta statement (FR-005)
└─ FooterSlot             Microsoft Game Content Usage Rules disclaimer (constitution X),
                          rendered by the route, reserved here so the panel is not vertically
                          centred against a footer that appears later and shifts it
```

`OutcomeRegion` sits **above** the action row, not below it. The user arrives back from Steam
looking at the top of the panel; an explanation under the button is an explanation after the
decision.

**IP note**: the Brandmark is an original geometric device — no crest, unit, building, portrait or
lettering from the game, and no Steam logo bitmap. The Steam button carries the word "Steam" as
text; naming a service is nominative use, shipping its mark is not, so the button has no icon slot
filled until a licence for the mark is recorded in this spec. Constitution X.

## 3. Variants and sizes

| Variant     | When                                                                 | Difference                                                                                                                                                                                                                                                                                |
| ----------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sign-in`   | visitor is not authenticated                                         | Title and button speak of signing in                                                                                                                                                                                                                                                      |
| `link`      | authenticated user adding a second Steam account (FR-007, `?link=1`) | Title: "Link another Steam account". The copy must **not** say "sign in" — the user already is. Adds the line: "Each Steam account has its own Age of Empires II profile. Linking a second one archives its replays too." Adds a `Cancel` (`Button/secondary`) returning to the dashboard |
| `returning` | the callback is being verified                                       | Everything below the title replaced by the loading state in §4                                                                                                                                                                                                                            |

One size. The panel is a single fixed composition; it does not have compact and comfortable forms.

## 4. States

Eight states, plus the four outcomes which are error-family states with distinct meanings.

**default** — Brandmark, title, value line, `Button/primary/lg` "Continue with Steam", no-admin
line, identity note, beta note. `OutcomeRegion` renders nothing (not an empty box: `Callout`'s empty
state, §Callout).

**hover / focus-visible / active** — owned entirely by `Button`. The panel itself has no hover
affordance and does not lift, glow or change fill: it is not a control.

**disabled** — the Steam button is disabled only when the sign-in route is not configured, and then
the beta note is replaced by a `Callout/info` saying sign-in is unavailable and when to try again. A
disabled button with no explanation is forbidden (`Button`, §disabled).

**loading** — two distinct loadings, and conflating them is the bug to avoid:

1. _Leaving_ — after the button is pressed, the `Button` enters its loading state with the label
   "Taking you to Steam…". The rest of the panel is untouched. Nothing else disables: if the
   redirect never happens the user must still be able to read the page.
2. _Returning_ (`returning` variant) — the callback is being verified server-side. Title stays;
   value line, action row and notes are replaced by three `Skeleton/text` lines and one
   `Skeleton/block` at the button's footprint, with a status line "Checking that with Steam…" in
   `text-secondary`. Per `Skeleton`, do not paint before 200 ms; after 10 s, fall through to the
   `unreachable` outcome below with a retry.

**error** — the four outcomes. Each is a `Callout` in `OutcomeRegion` with a heading, body, and an
action row that **always contains a way forward**. None of them ever leaves the user on a screen
whose only option is to close the tab.

| Outcome                                        | Callout tone | Heading                                                 | Body (normative)                                                                                                                                                                                                 | Actions                                                                                                                                               |
| ---------------------------------------------- | ------------ | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `no_aoe2_profile` (FR-003)                     | `info`       | This Steam account has no Age of Empires II profile yet | "Your sign-in worked. The game creates a profile the first time you play a match online — single-player games do not create one. If you have played online very recently, it can take a little while to appear." | "Try again" (`primary`), "Use a different Steam account" (`secondary`)                                                                                |
| `not_allowlisted` (FR-005)                     | `info`       | aoe2-stats is in closed beta                            | "Your sign-in worked. This Steam account is not on the beta list, so no account was created."                                                                                                                    | "Request access" (`primary`, **rendered only when a request route is configured** — a dead button is worse than no button), "Try again" (`secondary`) |
| `steam_assertion_invalid`                      | `danger`     | We could not verify that sign-in with Steam             | "Steam did not confirm the response we received, so we did not sign you in. This usually means the sign-in link was reused or has expired. Start again from the beginning."                                      | "Start over" (`primary`)                                                                                                                              |
| `unreachable`                                  | `danger`     | Steam did not answer                                    | "We could not reach Steam just now. Nothing about you was changed. This is almost always temporary."                                                                                                             | "Try again" (`primary`)                                                                                                                               |
| `profile_already_linked` (`link` variant only) | `warning`    | That Steam account is already linked elsewhere          | "This Steam account is linked to a different aoe2-stats account. Unlink it there first, or link a different one."                                                                                                | "Try a different account" (`primary`), "Cancel" (`secondary`)                                                                                         |

Copy rules for the outcomes, all verifiable in review:

- `no_aoe2_profile` and `not_allowlisted` are **explanations, not errors** — FR-003 says so in as
  many words. They use `info`, they never use the words "error", "failed", "invalid" or "sorry", and
  they open by confirming that the sign-in itself worked. The user did nothing wrong and the copy
  says so first.
- `steam_assertion_invalid` never shows technical detail: no OpenID parameter, no identifier, no
  status code, no stack. The server logs it (FR-001); the screen does not display it.
- `profile_already_linked` never names, hints at or counts the other account. FR-045: the person in
  front of us owns this Steam account, so telling them its own status is fine; describing the
  account it belongs to is not.
- No outcome offers "contact support" as the way forward for a lost Steam account. There is no such
  route, and implying one is the lie FR-006 exists to prevent.

**empty** — this screen's empty state is `OutcomeRegion` with no outcome, i.e. the ordinary first
visit. It renders **nothing** in that slot: no bordered box, no reserved grey rectangle, no "no
messages" text. The failure mode being ruled out is a visibly empty container in the default
screenshot.

## 5. Tokens used

Colour: `background` (page), `surface` (panel), `surface-raised` (callout), `border` (panel
boundary), `text-primary` (title, body, identity note), `text-secondary` (value line, no-admin line,
beta note, loading status), `accent` family (primary button, via `Button`), `info`, `warning`,
`danger` (callout tone), `focus-ring`.

Typography: family `display` for the title, `sans` everywhere else. Sizes — title `2xl` below `md` /
`3xl` from `md`; value line `md`; identity note `sm`; beta note, no-admin line `sm`; callout heading
`md`, callout body `sm`. Weights `bold` (title), `semibold` (callout heading), `normal` (body).
Tracking `tight` on the title.

Radius: `xl` (panel), `lg` (callout), `md` (buttons).
Elevation: `raised` on the panel, `none` on the callout.
Motion: `duration.fast` + `easing.standard` for button transitions; `duration.normal` +
`easing.decelerate` for an outcome appearing after a client-side transition. Under
`prefers-reduced-motion`, `duration.instant`.

Gaps in play: **DS-1** (light `accent` fill on the primary button — this screen is where it is most
visible), **DS-2** (`secondary` button boundary), **DS-4** (focus ring), **DS-6** (panel max width
and reading measure).

## 6. Spacing

All values are scale steps, never pixels.

| Between                        | Step                                                         |
| ------------------------------ | ------------------------------------------------------------ |
| Page gutter                    | `space-4` below `md`, `space-6` at `md`, `space-8` from `lg` |
| Panel padding                  | `space-6` below `md`, `space-8` from `md`                    |
| Brandmark to title             | `space-5`                                                    |
| Title to value line            | `space-3`                                                    |
| Value line to outcome region   | `space-6`                                                    |
| Outcome region to action row   | `space-6`                                                    |
| Action row to no-admin line    | `space-4`                                                    |
| No-admin line to identity note | `space-3`                                                    |
| Identity note to beta note     | `space-2`                                                    |
| Between sibling buttons        | `space-3`                                                    |
| Panel to footer slot           | `space-8`                                                    |

Vertical position: the panel is centred within the viewport's block axis from `md` up, with a
minimum block-start offset of `space-12` so it never collides with the top edge; below `md` it is
top-anchored at `space-8`, because centring a tall panel on a short phone hides the button under the
fold.

## 7. Responsive

- **375 (mobile)** — single column, panel spans the viewport minus `space-4` gutters, panel radius
  still `xl`. Buttons full width, stacked at `space-3`, recommended action first. Title `2xl`.
- **768 (tablet)** — panel max width around a 60–70 character measure (gap DS-6), horizontally
  centred, buttons intrinsic width on one row, left-aligned with the text. Title `3xl`.
- **1280 (desktop)** — identical to tablet. The panel does **not** grow with the viewport: a
  sign-in panel stretched to 1280px is unreadable, and there is no second column of content worth
  inventing to fill it.

Text is never centred except the title and the brandmark. Centred paragraphs are harder to scan and
this screen carries the identity statement.

## 8. Accessibility

- Landmark `<main>`; the panel is a `<section aria-labelledby>` pointing at the `<h1>`. Exactly one
  `<h1>` per page. Callout headings are `<h2>`.
- The Steam action is a `<button>` posting to the sign-in start route, or an `<a>` when it is a
  plain navigation. Never a `div`.
- **Focus after the callback**: when the screen mounts with an outcome, move focus to the callout
  heading (`tabindex="-1"`) so a screen-reader user lands on the explanation rather than at the top
  of a page that looks unchanged. Do this once, on mount, and never steal focus again afterwards.
- `Callout` roles: `role="status"` for `info` / `warning`, `role="alert"` for `danger`. Because
  focus is moved on mount, do not additionally wrap the region in `aria-live` — that announces
  twice.
- Keyboard order equals visual order: outcome, then actions, then notes. No positive `tabindex`.
- Touch targets ≥ 44px: buttons render at `lg` (48px) below `md`.
- Contrast: all text meets AA per the README table. `warning` and `accent` are never used for
  normal-size text in the light theme; body text in every callout is `text-primary`.
- The identity note is real text in `text-primary`, not a tooltip, not a `<details>`, not a
  `title=` attribute.
- The screen is fully usable at 200% browser zoom and at 320px logical width without horizontal
  scrolling.

## 9. Visual acceptance criteria

Verifiable from a screenshot; this is the list `visual-reviewer` works through.

**Default (both themes, 375 / 768 / 1280)**

- [ ] Exactly one primary button is visible, and its label reads "Continue with Steam".
- [ ] No empty bordered box or reserved grey rectangle sits where an outcome would appear.
- [ ] The identity note is visible without any interaction, in the primary text colour, and states
      that the Steam account is the only key and that access cannot be recovered.
- [ ] The closed-beta note is visible.
- [ ] The panel is horizontally centred and does not span the full 1280px viewport.
- [ ] No Age of Empires or Steam artwork, logo, portrait, unit, building or in-game font appears
      anywhere in the frame.

**Failure outcomes (one screenshot per outcome, both themes)**

- [ ] `no_aoe2_profile` and `not_allowlisted` render in the info tone: a blue-grey stripe, not red,
      and no word from the set {error, failed, invalid, sorry} appears.
- [ ] Every outcome screenshot contains at least one enabled button.
- [ ] `steam_assertion_invalid` renders in the danger tone and shows no identifier, parameter,
      status code or stack trace.
- [ ] Callout body text is the primary text colour, not the tone colour, in both themes.
- [ ] No outcome mentions contacting support to regain access to a Steam account.

**Loading**

- [ ] The pressed button shows a spinner, a present-participle label and the same width as at rest.
- [ ] The `returning` variant shows skeleton blocks whose footprint matches the default layout —
      overlaying the two screenshots shows no reflow — and contains no `0` or placeholder numeral.

**Focus and keyboard**

- [ ] A focus ring is clearly visible on the focused button, offset from its edge, in both themes.
- [ ] The ring is the focus-ring colour, not the accent colour, and is not clipped by the panel.

**Density and craft**

- [ ] Every interactive element measures at least 44px in its smallest dimension at 375px.
- [ ] No text is centred except the title.
- [ ] The panel casts the raised elevation only; nothing else in the frame carries a shadow.
