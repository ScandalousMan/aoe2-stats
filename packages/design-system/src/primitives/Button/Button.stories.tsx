import type { Meta, StoryObj } from '@storybook/react-vite'
import { Callout } from '../Callout'
import { Button } from './index'

const meta: Meta<typeof Button> = {
  id: 'primitives-button',
  title: 'Primitives/Forms/Button',
  component: Button,
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

// §Button "focus-visible": the standard ring, reached by the keyboard only — never by a pointer
// click (that is what makes it `:focus-visible` rather than `:focus`).
export const FocusVisible: Story = {
  args: { variant: 'primary', size: 'lg' },
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
