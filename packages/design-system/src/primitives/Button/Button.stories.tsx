import type { Meta, StoryObj } from '@storybook/react-vite'
import { Callout } from '../Callout'
import { Button } from './index'

const meta: Meta<typeof Button> = {
  id: 'primitives-button',
  title: 'Primitives/Forms/Button',
  component: Button,
  parameters: {
    docs: {
      description: {
        component: `Commits the user to an action, with visual weight matching how consequential and how recommended it is.`,
      },
    },
  },
  args: {
    children: 'Continue with Steam',
  },
}

export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: { variant: 'primary', size: 'lg' },
}

export const Secondary: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
}

export const Ghost: Story = {
  args: { variant: 'ghost', children: 'Manage' },
}

export const Destructive: Story = {
  args: { variant: 'destructive', children: 'Unlink this profile' },
}

export const Loading: Story = {
  args: { variant: 'primary', size: 'lg', loading: true, loadingLabel: 'Taking you to Steam…' },
}

export const Disabled: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-2">
      <Button variant="primary" size="lg" disabled>
        Continue with Steam
      </Button>
      <p className="text-text-secondary text-sm">Sign-in is not configured right now.</p>
    </div>
  ),
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}

export const AsLink: Story = {
  args: { variant: 'secondary', href: '#', children: 'Read the privacy notice' },
}

// shared-primitives.md §Button "hover": fill deepens to `accent-hover`, colour only — a still
// capture of the real `:hover` pseudo-class. `tests/visual/stories.spec.ts` drives the real state
// from Playwright, in a real browser, once this story has settled — a `play()` here could only
// dispatch a synthetic event, which every one of Chromium's `:hover`/`:active`/`:focus-visible`
// pseudo-classes ignores (see that file's own `VisualForceState` comment for the measurement).
export const Hover: Story = {
  args: { variant: 'primary', size: 'lg' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

// README's gap register row 8 (H5), F13 (root cause of F1, F2, F4, F6, F7): before this trio,
// `Hover` above hard-coded `variant: 'primary'`, so `secondary|md` and `destructive|md` had no
// hover frame anywhere in the tree, and every spec sentence deferring a non-`primary` button's
// hover "to `Button`'s stories" was false at that size — `secondary`'s own hover only ever existed
// elsewhere, at `lg` (`ReplayAvailabilityList:Hover`), and `destructive`'s not at all. Same shape
// as `SecondaryFocusVisible`/`GhostFocusVisible`/`DestructiveFocusVisible` below (T587): one story
// per variant, each proving the fill deepens to `accent-hover`-shaped tone regardless of which
// variant it sits on. `ghost|md`'s own hover was already covered elsewhere
// (`FavouriteToggle:Hover`) before this story existed; `GhostHover` gives it the same first-party
// frame the other two variants get here, for the same reason `GhostFocusVisible`/`GhostActive`
// already do — not because the cell was open.
export const SecondaryHover: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const GhostHover: Story = {
  args: { variant: 'ghost', children: 'Manage' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const DestructiveHover: Story = {
  args: { variant: 'destructive', children: 'Unlink this profile' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

// §Button "focus-visible": the standard ring, reached by the keyboard only — never by a pointer
// click (that is what makes it `:focus-visible` rather than `:focus`).
export const FocusVisible: Story = {
  args: { variant: 'primary', size: 'lg' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'button' } },
}

// Widened 2026-09-12 (README's gap register row 5/H2, `visual-reviewer` pass): before this story,
// `FocusVisible` above hard-coded `variant: 'primary'`, so no baseline ever showed a focused
// `secondary`, `ghost` or `destructive` button — the shared outward `focus-ring` those three keep
// was evidenced only by a code read. One story per variant, matching this file's own convention for
// `active` (`SecondaryActive`/`DestructiveActive`/`GhostActive` below), each proving the same ring
// paints regardless of the fill or border it sits on.
export const SecondaryFocusVisible: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'button' } },
}

export const GhostFocusVisible: Story = {
  args: { variant: 'ghost', children: 'Manage' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'button' } },
}

export const DestructiveFocusVisible: Story = {
  args: { variant: 'destructive', children: 'Unlink this profile' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'button' } },
}

// §Button "active": `accent-active`, the third of three deliberately distinct fills (rest, hover,
// press) — held down rather than released so the capture shows the pressed frame.
export const Active: Story = {
  args: { variant: 'primary', size: 'lg' },
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}

// Sixth-pass review remediation (B2): before this story, no baseline anywhere captured a pressed
// non-primary `Button` on its own account — the only one in the whole suite was a side effect of
// `composite-replayavailabilitylist`'s own story, which exercises `ReplayAvailabilityList`, not
// `Button` directly. That is how the dead `active:outline-2` classes (see `index.tsx`'s own
// comment for the trap) shipped as "verified": no test could fail from a change to
// `variantClasses.secondary`, because no baseline captured it. This story, `DestructiveActive` and
// `GhostActive` below are the proof — each must render a press visibly different from the same
// variant's own resting frame (`Secondary`/`Destructive`/`Ghost` above), a `box-shadow` ring
// (`active:ring-2 active:ring-border-strong` for `secondary`) flush against the permanent border.
export const SecondaryActive: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}

// Sixth-pass review remediation (B2): `destructive`'s own pressed frame — `active:ring-2
// active:ring-danger`, the same box-shadow-backed technique as `SecondaryActive`, in the boundary
// token this variant already carries at every state (`border-danger`).
export const DestructiveActive: Story = {
  args: { variant: 'destructive', children: 'Unlink this profile' },
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}

// Sixth-pass review remediation (B2): `ghost`'s own pressed frame. Unlike `secondary`/
// `destructive`, `ghost`'s active technique was never the defect B1 found — it starts from
// `border-transparent` at rest and paints `border-border-strong` only at `active` (the same
// reserve-then-paint technique `Menu`/`Table`/`MatchRow`/`PlayerResultRow`/`FavouritesList` use),
// a real `border` the whole time, never an `outline`. This story exists for the same reason the
// other two do: FR-042 asks a named story per variant per applicable state, and none of `ghost`'s
// three states had one of its own before this remediation either.
export const GhostActive: Story = {
  args: { variant: 'ghost', children: 'Manage' },
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}

// §Button "error": "the button has no error state of its own. The failure renders in a `Callout`
// beside or above it and the button returns to `default` and to being pressable" — shown here
// rather than only described, so the answer is a picture rather than a sentence to trust.
export const ErrorNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      <Callout tone="danger" heading="We could not verify that sign-in with Steam">
        Steam did not confirm the response we received, so we did not sign you in. Start again from
        the beginning.
      </Callout>
      <Button variant="primary" size="lg">
        Continue with Steam
      </Button>
    </div>
  ),
}

// §Button "empty": "not applicable: a button with no label is invalid" — there is no rendering to
// show, so the answer is words rather than a blank button.
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A `Button` with no label is invalid — there is no icon-only form on the primary path of any
      screen in this feature, so this state has no rendering to show.
    </p>
  ),
}

// A realistic combined story: `DashboardContainer.tsx`'s own `Page` actions — two `ghost` buttons
// side by side, real labels at real lengths ("Search players", "Sign out"), never a single
// isolated specimen.
export const RealisticPageActions: Story = {
  name: 'Realistic composition — Page actions (DashboardContainer)',
  render: () => (
    <div className="flex items-center gap-3">
      <Button variant="ghost" size="lg">
        Search players
      </Button>
      <Button variant="ghost" size="lg">
        Sign out
      </Button>
    </div>
  ),
}

// README's gap register row 8 (H5): the `href`-rendered `<a>` form (index.tsx:189) shares
// `variantClasses`/`focusRing` with the `<button>` form, but no story before this trio ever forced
// a state on it — `AsLink` above renders it at rest only, and every `Hover`/`FocusVisible`/`Active`
// story elsewhere on this page targets `role: 'button'`, which an anchor never carries. `role:
// 'link'` needs no `name`: this story's own anchor is the only link `Button` renders. Appended
// here, after every other export, so it never shifts this file's own cited line numbers in
// README.md's row 8 (H5) table.
export const AsLinkHover: Story = {
  args: { variant: 'secondary', href: '#', children: 'Read the privacy notice' },
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
}

export const AsLinkFocusVisible: Story = {
  args: { variant: 'secondary', href: '#', children: 'Read the privacy notice' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'link' } },
}

export const AsLinkActive: Story = {
  args: { variant: 'secondary', href: '#', children: 'Read the privacy notice' },
  parameters: { visualForceState: { state: 'active', role: 'link' } },
}

// README's gap register row 8 (H5), Cause A, closed by T600: `resolveClassParts`'s own class-half
// (row 8's own Method section, "Record 1's own class half") reads only a `Button` element's
// *default* variant's class, so record 3's own axis matrix — which does resolve every real
// `variant|size` combination the tree renders, independent of that limitation — is where
// `primary|md`'s own hover/press live. This pass hand-traced `variantClasses.primary`
// (`index.tsx`), which paints identically at every size: only `sizeClasses` (padding/height/type
// scale) varies by size, never a state class, so `primary|md`'s own hover/press are the same
// `hover:bg-accent-hover`/`active:bg-accent-active` recipe `Hover`/`Active` above already prove at
// `lg` — a real, distinct-from-rest treatment nothing before this pair ever forced at `md`. `size`
// omitted (defaults `'md'`, `index.tsx`'s own destructuring), matching `SecondaryHover`/
// `GhostHover`/`DestructiveHover`'s own convention for their variant's non-`lg`-labelled stories.
export const PrimaryHoverMd: Story = {
  args: { variant: 'primary' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const PrimaryActiveMd: Story = {
  args: { variant: 'primary' },
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}

// README's gap register row 8 (H5), Cause A, closed by T600: `ghost|lg` had no hover, focus-visible
// or press frame anywhere in the tree — `RealisticPageActions` above renders two `ghost` buttons at
// `lg` but forces no state on either. `variantClasses.ghost`/`focusRing` (`index.tsx`) paint the
// same class set regardless of size, the same fact `PrimaryHoverMd`'s own comment traces for
// `primary` — so this is the same, real `hover:bg-surface-sunken`/`focus-visible:outline-2 …
// focus-visible:outline-focus-ring`/`active:bg-background active:border-border-strong` recipe
// `GhostHover`/`GhostFocusVisible`/`GhostActive` above already prove at `md`, now forced at `lg`.
//
// With no `tags: ['visual-full-page']`, the default capture is a screenshot of `root` itself — but
// `root` here renders as Storybook's padded story canvas, not the button's own box, so a
// boundary-only signal (`focus-visible`'s outline; `active`'s border swap from `transparent`) is a
// small mark against a mostly unchanged frame, the same reason `Dialog`'s `Hover`/`Active` clip.
// `GhostFocusVisibleLg` and `GhostActiveLg` below clip to the button itself, the same
// `PRIMARY_ACTION_CLIP` idiom `Dialog.stories.tsx` uses. `GhostHoverLg` does not; whether it needs
// one, like the rest of this file's states, is T675's to determine (README's Verification-coverage
// gap register).
const GHOST_LG_CLIP = { parts: [{ role: 'button' as const, name: 'Manage' }], pad: '2' }

export const GhostHoverLg: Story = {
  args: { variant: 'ghost', size: 'lg', children: 'Manage' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const GhostFocusVisibleLg: Story = {
  args: { variant: 'ghost', size: 'lg', children: 'Manage' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button' },
    visualCaptureClip: GHOST_LG_CLIP,
  },
}

export const GhostActiveLg: Story = {
  args: { variant: 'ghost', size: 'lg', children: 'Manage' },
  parameters: {
    visualForceState: { state: 'active', role: 'button' },
    visualCaptureClip: GHOST_LG_CLIP,
  },
}
