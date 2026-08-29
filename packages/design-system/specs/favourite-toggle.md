# FavouriteToggle

**Component**: `src/components/FavouriteToggle/`
**Feature**: 003, US5 — consumed by `apps/web/src/routes/players.$profileId.tsx` (003 T349), where
[`profile-summary.md`](./profile-summary.md) §11.1 point 3 already reserves its place in `IdentityBar`,
and reused in a trailing position by [`favourites-list.md`](./favourites-list.md)'s `FavouriteRow` for
per-entry removal.
**Requirements**: FR-012, FR-013, FR-015, FR-016. US5 scenarios 1, 2, 5.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button` (this is a `Button/ghost`
with `aria-pressed`, never a bespoke control), `Callout`. [`sign-in-screen.md`](./sign-in-screen.md) —
the destination the signed-out state routes to, carrying the caller's place.

## 1. Purpose

Let a signed-in user mark any player as a favourite, or unmark them, from that player's profile in one
gesture (FR-013) — and, when the user is not signed in, ask them to sign in and return them to exactly
where they were, rather than dropping the action or their place (US5 scenario 5).

## 2. Anatomy

```
FavouriteToggle                                     one per third-party profile; never on subject="self"
├─ Control            Button/ghost, aria-pressed reflecting favourited state — the whole affordance
│  ├─ StateGlyph      optional, aria-hidden, original mark (see IP note) — outline when unmarked,
│  │                  filled when marked; decorative, never the sole carrier of the state
│  └─ Label           text, the authoritative carrier of state (§3): "Add to favourites" /
│                     "Remove from favourites" / the bounded and signed-out labels in §5
└─ Explanation        text-secondary, present only in the bounded and disabled cases (Button's own
                      "a disabled control must say why" rule) and in no other state
```

The error surface a failed `PUT`/`DELETE` needs is **not** part of this anatomy — it is a `Callout`
the consuming layout renders beside or above the control, exactly as `Button` (§error) requires: the
button owns no error state of its own, so a failure never leaves it stuck disabled (§5).

**IP note**: `StateGlyph`, if drawn at all, is an original geometric bookmark/pin device — no star,
crest, unit, portrait or lettering from the game, and no third-party icon set unless its free licence
is recorded here before first use. The state is always fully carried by `Label` text, so the glyph may
be omitted entirely with no loss of meaning (constitution VI, README rule 4). Constitution X.

## 3. Variants and sizes

No variant axis of its own — the control is one `Button/ghost`, and every difference below is a
**state** driven by two inputs the consumer supplies (§4), never a separate variant. Sizes are
`Button`'s own: `md` is pointer-only, and any touch viewport renders `lg` (48px) or `md` with the hit
area padded to 44px, per `shared-primitives.md`'s `Button` rule. This component adds no size axis.

## 4. The two inputs that decide every state, and the one thing this control must never do

`FavouriteToggle` is fed exactly what it needs to render a state and nothing it could misuse:

- `favourited: boolean` — whether this profile is in the caller's own favourites. When the caller is
  signed out this is not `false`, it is **unknowable** (`authenticated: false` below), and the two must
  never collapse: FR-015 keeps favourites private, so a signed-out visitor is never told a favourited
  state exists at all.
- `authenticated: boolean` — whether a session exists. Drives the signed-out state in §5.
- `atLimit: boolean` — whether the caller's favourites are at the configured bound (FR-016). Supplied
  by the consumer from the count `GET /api/favourites` returns against the configured maximum; **this
  component never computes the bound and never receives the maximum as anything but a number to show**
  in the explanation copy. `atLimit` only affects the unmarked→add direction (§5): removing is always
  permitted, so a `favourited` profile is never blocked by the bound.

**This control triggers exactly one thing: the favourites `PUT`/`DELETE` (FR-013), and never a
capture.** Marking a player is a private bookmark with no consequence beyond the `favourites` table
(FR-012, FR-015, US5 scenario 4). `FavouriteToggleProps` carries no prop, today or later, that could
enqueue ingestion, archival or any read of the player's recorded games — there is deliberately nothing
in the component's own type for such a side effect to be wired to, the same enforcement
`player-search.md` §4 states for the fields that must not exist.

## 5. States

The state vocabulary is closed (README); every one is answered. Two of them — **bounded** and
**signed-out** — are the ones US5 and FR-016 name explicitly and are the reason this control is
specified rather than assembled from a bare `Button`.

**default (unmarked) — `authenticated: true`, `favourited: false`, `atLimit: false`.** `Button/ghost`,
`aria-pressed="false"`, label **"Add to favourites"**, `StateGlyph` in its outline form. Activating it
issues `PUT /api/favourites/{profile_id}`.

**default (marked) — `authenticated: true`, `favourited: true`.** `Button/ghost`, `aria-pressed="true"`,
label **"Remove from favourites"**, `StateGlyph` filled. Activating it issues
`DELETE /api/favourites/{profile_id}`. The label — not colour, not the glyph — is what tells the two
apart, so the state survives greyscale, a screen reader, and the glyph being omitted (README rule 4).
The control is `accent`-free: a ghost button never fills with `accent` at rest, and the marked state
is not signalled by tinting the button, only by its `aria-pressed`, its label and its glyph.

**bounded — `authenticated: true`, `favourited: false`, `atLimit: true` (FR-016).** The add direction
cannot succeed, so the control is **disabled with a reason present**, never a bare greyed button
(`Button`'s §disabled rule). Label stays "Add to favourites"; `disabled` is set; `Explanation` renders
beneath in `text-secondary`: _"You've reached your favourites limit of `<max>`. Remove one to add
another."_ — the max shown as the plain number the consumer supplied (§4). A profile that is already
`favourited` is **never** in this state: removal is always allowed, so the marked default above still
renders and still works at the bound.

**hover / focus-visible / active** — owned entirely by `Button/ghost` (`surface-sunken` hover fill,
standard `focus-ring` at `outline-offset-2`, `surface-sunken` + `border-strong` active). The profile
header around it does not add a second hover. In the bounded/disabled case there is no hover.

**disabled** — the bounded state above is the only disabled condition, and it always carries its
`Explanation`. There is no other reason this control is ever disabled; a disabled toggle with no reason
beside it is forbidden (`Button`, DS-3).

**loading** — while a `PUT` or `DELETE` is in flight: `Button`'s own loading state (`aria-busy`,
`disabled` for the duration, width unchanged by reserving the glyph slot), with a caller-supplied
present-participle label — **"Adding…"** for `PUT`, **"Removing…"** for `DELETE`. The label and glyph
flip to the new state only on the `200`, never optimistically before it, so a failed request never
leaves the control asserting a favourited state the server did not record.

**error** — the `PUT`/`DELETE` failed; `Button` returns to its previous default and stays pressable
(never stuck disabled — the most common way a retry becomes unreachable), and a `Callout` renders in
the consumer's error slot (§2). Two distinct causes, never one message:

1. _Bound race_ (`409 favourites_limit_reached` arriving on a click that §4's `atLimit` had shown as
   `false` — another tab or device added a favourite since this page loaded): `Callout/warning` —
   _"You've reached your favourites limit of `<max>`. Remove one to add another."_ The control reverts
   to unmarked and, on the next render with a refreshed count, moves to the **bounded** state above.
   `warning`, not `danger`: nothing failed in this service — a real, truthful limit was hit
   (`shared-primitives.md`'s tone rule).
2. _Request failed_ (network, or this service's API unavailable): `Callout/danger` — _"We could not
   update your favourites. Try again."_ The control returns to its pre-click state so a retry repeats
   the same intended action.

**empty** — not applicable, and stated rather than skipped: a toggle with no label is invalid, the
same as `Button` (§empty). Every state above renders a label; there is no zero-content form of this
control. The nearest thing to "empty" — a profile the control should not appear on at all — is
`subject="self"`, where `profile-summary.md` §11.1 point 3 makes the toggle **absent, not disabled**:
a user cannot favourite their own profile and the API gives no route to try.

### 5a. signed-out — `authenticated: false` (US5 scenario 5, FR-015)

The affordance is still **discoverable** — the control renders — but it can neither read nor assert a
favourited state, because FR-015 forbids disclosing one to a visitor with no session. So:

- `aria-pressed` is **absent** (not `"false"`): the control makes no claim about a favourited state it
  cannot know, and a signed-out visitor is never shown one player as favourited and another not.
- Label reads **"Sign in to add favourites"**, `StateGlyph` in its neutral outline form. No bounded
  explanation renders — the bound is a property of a session that does not exist here.
- Activating it does **not** call the favourites API (a signed-out `PUT` would only earn the
  `401 sign_in_required` the client already anticipates). It routes to `sign-in-screen.md` **carrying
  the caller's current location** — the exact profile URL — so that after a successful sign-in the user
  is returned to this same profile, where they were, with the toggle now in its authenticated default
  (US5 scenario 5: "returned to where they were"). The return-to-place is the whole point of this
  state: the `401 sign_in_required` code the API defines
  (`contracts/http-api.md`) exists precisely so the client never loses the user's place, and this
  control never strands them on the sign-in screen with no way back.
- Re-applying the pending mark after return is **app wiring, not a visual guarantee this component
  makes**: the requirement US5 states is return-to-place, and that is what the routing above delivers;
  whether the deferred favourite is then replayed automatically is left to the feature's own state, not
  asserted on screen, so no favourited state is ever shown before a real `200` records it.

Under the closed-beta allowlist this path is currently unreachable in production (spec.md Assumptions:
"whether any of it is reachable without signing in is deferred… the beta allowlist makes the question
moot"), and it is specified in full anyway, because the requirement (US5 scenario 5) is written against
it and the state must exist the moment the allowlist is lifted, not be invented then.

## 6. Tokens used

Colour, all via `Button/ghost` and `Callout`, no new token and no new pair (every one is already in
`specs/README.md`'s measured table and asserted in `tokens/build-tokens.test.mjs`): `surface`
(page/header behind the ghost control), `surface-sunken` (`Button` hover/active fill, disabled fill),
`surface-raised` (`Callout` fill, via that component), `border` (disabled boundary), `border-strong`
(active boundary), `text-primary` (resting label), `text-secondary` (`Explanation`, and the disabled
label via `text-disabled`), `text-disabled` (bounded/disabled label), `warning` / `danger` (the two
`Callout` tones in §5), `focus-ring`. **No `accent`**: this control never fills with `accent`, in
either state — the marked state is carried by label, `aria-pressed` and glyph, not by tinting a ghost
button, so the one place `accent` legitimately appears (a `primary` action) is never confused with a
toggle that happens to be on.

Typography: `sans` throughout, size `sm` label (`Button/md`) or `md` (`Button/lg` on touch), weight
`semibold` (`Button`'s own), `Explanation` `sm` `normal`. `StateGlyph` sizes from the adjacent
font-size (`1em`, gap DS-7), never a fixed pixel size.

Radius `md` (`Button`), `lg` (`Callout`, via that component). Elevation `none` — a button does not
float, and neither does its error callout (`shared-primitives.md`). Motion `duration.fast` +
`easing.standard` on the ghost hover/active transition and on the glyph's outline↔filled swap; **the
glyph never animates on entry and the label never counts or fades** (README rule 1). Under
`prefers-reduced-motion`, `duration.instant` and the glyph swaps with no transition.

Gaps in play: **DS-4** (focus ring), **DS-7** (`StateGlyph` sizing from the font). No new gap.

## 7. Spacing

| Between                                    | Step      |
| ------------------------------------------ | --------- |
| `StateGlyph` to `Label` (inside `Button`)  | `space-2` |
| `Control` to `Explanation` (bounded state) | `space-1` |
| `Control` to its error `Callout` (§5)      | `space-2` |

All other internal spacing is `Button/ghost`'s own (`shared-primitives.md` §Button); this component
introduces no arbitrary value.

## 8. Responsive

- **375** — the control is `Button`'s touch size (`lg`, 48px, clearing 44px), full width of its slot
  in `IdentityBar` when it is the sole action there, or intrinsic width beside a sibling per `Button`'s
  own responsive rule. `Explanation`, when present, wraps onto its own line beneath and never truncates
  (`profile-summary.md`'s "never ellipsise" extended to this reason string).
- **768** — intrinsic width, sitting where `profile-summary.md` §11.1 places it in `IdentityBar`
  (replacing `ProfileActions`' position). `Explanation` sits beneath the control, not squeezed onto its
  line.
- **1280** — unchanged from 768; there is no wider layout for a single toggle to grow into.

The label text is identical at every viewport — it is never shortened to an icon-only control on small
screens (`shared-primitives.md`: an icon-only button is forbidden on the primary path), so the state
stays readable as words at 375px.

## 9. Accessibility

- A real `<button type="button">` with `aria-pressed` reflecting the favourited state in the
  authenticated default states, and **`aria-pressed` absent** in the signed-out state (§5a) — the
  control makes no toggle claim it cannot back with a session.
- The label is the accessible name and changes with the state ("Add to favourites" / "Remove from
  favourites" / "Sign in to add favourites"); the state is **never** communicated by `StateGlyph` or
  colour alone — the glyph is `aria-hidden` and adds nothing not already in the label (README rule 4,
  constitution VI).
- Space and Enter activate; touch target ≥ 44px (`Button`'s own rule; `lg` on touch viewports).
- The bounded/disabled state carries its `Explanation` as real text next to the control, associated via
  `aria-describedby`, so a screen-reader user learns why it is disabled at the same moment it stops
  responding (`Button` §disabled, DS-3).
- The error `Callout` follows `Callout`'s tone-to-role mapping — `role="status"` for the `warning`
  bound-race case, `role="alert"` for the `danger` request-failure case (`shared-primitives.md`).
- The signed-out control's sign-in navigation is a real activation that changes location; it is not a
  silent no-op, so a keyboard or screen-reader user reaches the sign-in screen the same way a pointer
  user does, and returns to the same profile afterwards (§5a).
- Contrast per `specs/README.md`'s measured table, entirely through `Button/ghost` and `Callout`, which
  already carry those obligations. `text-disabled` fails AA by design (DS-3); the bounded state
  therefore never puts information **only** in the disabled label — the `Explanation` beside it, in
  `text-secondary`, carries the reason.
- Usable at 200% zoom and 320px logical width without horizontal scrolling; the label never truncates.

## 10. Visual acceptance criteria

- [ ] The unmarked story shows a ghost button reading "Add to favourites" with `aria-pressed="false"`;
      the marked story reads "Remove from favourites" with `aria-pressed="true"` — confirmed to differ
      by **label text**, not colour, by converting both frames to greyscale and still telling them
      apart.
- [ ] No story renders the marked state as an `accent`-filled button; the toggle is a ghost control in
      both resting states, distinguished only by label, `aria-pressed` and (if present) the glyph's
      outline-vs-filled form.
- [ ] The bounded story (`atLimit: true`, unmarked) shows the button **disabled with a visible
      explanation** naming the limit number beside it — never a bare greyed button with no reason.
- [ ] A marked profile at the bound (`atLimit: true`, `favourited: true`) still shows an **enabled**
      "Remove from favourites" control — removal is never blocked by the bound.
- [ ] The signed-out story shows a control reading "Sign in to add favourites" with **no** `aria-pressed`
      attribute and **no** favourited state implied anywhere in the frame (FR-015), and activating it in
      the story navigates to the sign-in screen carrying the profile's location — never a silently dead
      button and never a `PUT` fired without a session.
- [ ] The loading story shows a spinner with an "Adding…"/"Removing…" label at the same width as at
      rest, and the label/glyph flip to the new state only after the success is seeded — never before.
- [ ] The request-failed story shows a `danger` callout beside a control that is **back to pressable**,
      not stuck disabled; the bound-race story shows a `warning` callout and the control reverting to
      the bounded state.
- [ ] No `subject="self"` story renders this control at all (cross-checked against
      `profile-summary.md` §11.4's equivalent criterion) — it is absent, not disabled.
- [ ] No star, crest, portrait, unit or in-game font appears in any frame — at most an original,
      `aria-hidden` bookmark glyph, and the state stays legible with the glyph removed.
