import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { Callout } from '../../primitives/Callout'
import { FavouriteToggle } from './index'

const meta: Meta<typeof FavouriteToggle> = {
  id: 'composite-favouritetoggle',
  title: 'Composites/Search & favourites/FavouriteToggle',
  component: FavouriteToggle,
}

export default meta
type Story = StoryObj<typeof FavouriteToggle>

export const Unmarked: Story = {
  args: { favourited: false, authenticated: true },
}

export const Marked: Story = {
  args: { favourited: true, authenticated: true },
}

// FR-016 — the add direction cannot succeed, so the control is disabled with a reason present,
// never a bare greyed button.
export const Bounded: Story = {
  name: 'Bounded — at the favourites limit (FR-016)',
  args: { favourited: false, authenticated: true, atLimit: true, max: 100 },
}

// §5: removal is always permitted, so a favourited profile at the bound still shows an enabled
// "Remove from favourites" control.
export const MarkedAtLimit: Story = {
  name: 'Marked, and also at the limit — removal is never blocked',
  args: { favourited: true, authenticated: true, atLimit: true, max: 100 },
}

export const AddingInFlight: Story = {
  name: 'Loading — a PUT is in flight ("Adding…")',
  args: { favourited: false, authenticated: true, loading: true },
}

export const RemovingInFlight: Story = {
  name: 'Loading — a DELETE is in flight ("Removing…")',
  args: { favourited: true, authenticated: true, loading: true },
}

// §5a, US5 scenario 5, FR-015 — discoverable but asserts no favourited state; a real activation
// that carries the caller's own profile location to the sign-in screen and back.
export const SignedOut: Story = {
  name: 'Signed out (§5a, FR-015)',
  args: {
    favourited: false,
    authenticated: false,
    signInHref: '/sign-in?returnTo=%2Fplayers%2F12345',
  },
}

// §5 "error" — bound race: another tab or device favourited a player since this page loaded. The
// Callout composition below is the consumer's own layout (§2: the error surface is not part of
// this component's anatomy), shown here to demonstrate the intended pairing.
export const BoundRaceError: Story = {
  name: 'Error — bound race (409 favourites_limit_reached, consumer-composed Callout)',
  render: () => (
    <div className="flex flex-col items-start gap-2">
      <FavouriteToggle favourited={false} authenticated />
      <Callout
        tone="warning"
        heading="You've reached your favourites limit of 100."
        headingLevel={3}
      >
        Remove one to add another.
      </Callout>
    </div>
  ),
}

// §5 "error" — the request itself failed (network, or this service's API unavailable). The
// control returns to its pre-click state and stays pressable, never stuck disabled.
export const RequestFailedError: Story = {
  name: 'Error — request failed (consumer-composed Callout)',
  render: () => (
    <div className="flex flex-col items-start gap-2">
      <FavouriteToggle favourited={false} authenticated />
      <Callout
        tone="danger"
        heading="We could not update your favourites. Try again."
        headingLevel={3}
      />
    </div>
  ),
}

// favourite-toggle.md §5 "hover / focus-visible / active — owned entirely by `Button/ghost`... In
// the bounded/disabled case there is no hover." Forced here on the enabled control.
export const Hover: Story = {
  args: { favourited: false, authenticated: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.hover(canvas.getByRole('button'))
  },
}

export const FocusVisible: Story = {
  args: { favourited: false, authenticated: true },
  play: async () => {
    await userEvent.tab()
  },
}

export const Active: Story = {
  args: { favourited: false, authenticated: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const button = canvas.getByRole('button')
    await userEvent.pointer({ keys: '[MouseLeft>]', target: button })
  },
}

// §5 "empty — not applicable... a toggle with no label is invalid, the same as `Button`. Every
// state above renders a label; there is no zero-content form of this control."
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A toggle with no label is invalid, the same as `Button` — every state renders a label, so
      there is no zero-content form of this control to show.
    </p>
  ),
}

// A realistic combined story: beside a third party's profile heading, its actual seam
// (`PlayerProfileContainer.tsx` wires this into `ProfileSummary`'s own `favouriteToggle` slot, at
// `size="lg"` per §11.1 point 3), never rendered as an isolated specimen.
export const RealisticProfileHeader: Story = {
  name: 'Realistic composition — beside a third-party profile heading (PlayerProfileContainer)',
  render: () => (
    <div className="flex items-center gap-3">
      <h1 className="type-display text-2xl font-semibold text-text-primary">rival_ace</h1>
      <FavouriteToggle favourited={false} authenticated size="lg" />
    </div>
  ),
}

// A realistic combined story: every state side by side, so the label/aria-pressed/glyph
// distinction (never colour alone) is checkable in one frame.
export const AllStates: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-4">
      <FavouriteToggle favourited={false} authenticated />
      <FavouriteToggle favourited authenticated />
      <FavouriteToggle favourited={false} authenticated atLimit max={100} />
      <FavouriteToggle favourited authenticated atLimit max={100} />
      <FavouriteToggle favourited={false} authenticated loading />
      <FavouriteToggle favourited authenticated loading />
      <FavouriteToggle favourited={false} authenticated={false} signInHref="/sign-in" />
    </div>
  ),
}
