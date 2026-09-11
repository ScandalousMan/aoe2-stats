import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { StatValue } from './index'

const meta: Meta<typeof StatValue> = {
  id: 'primitives-statvalue',
  title: 'Primitives/Feedback & status/StatValue',
  component: StatValue,
}

export default meta
type Story = StoryObj<typeof StatValue>

export const Hero: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1842',
    delta: { value: 12 },
    secondaryLine: 'Measured 3 minutes ago',
  },
}

export const Compact: Story = {
  args: { variant: 'compact', label: 'Rank', value: '#214' },
}

export const Inline: Story = {
  args: { variant: 'inline', label: 'Win rate', value: '54%' },
}

export const NegativeDelta: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1802',
    delta: { value: -8 },
  },
}

// `status: 'loading'` renders `Skeleton`, which stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    status: 'loading',
    loadingWidthClassName: 'w-24',
  },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

export const EmptyNeverObserved: Story = {
  args: {
    variant: 'compact',
    label: 'Rank',
    status: 'empty',
    secondaryLine: 'Not ranked yet',
  },
}

// T532: no caller-supplied reason at all — the generic, always-true default, never a punctuation
// mark and never a fabricated specific claim.
export const EmptyGenericDefault: Story = {
  args: {
    variant: 'compact',
    label: 'Streak',
    status: 'empty',
  },
}

// T532: an explicit `emptyReason` and a distinct `secondaryLine` compose independently.
export const EmptyWithExplicitReason: Story = {
  args: {
    variant: 'inline',
    label: 'Win rate',
    status: 'empty',
    emptyReason: 'Never played this leaderboard',
    secondaryLine: 'Checked 3 minutes ago',
  },
}

// shared-primitives.md §StatValue "error — the last known value renders, with the secondary line
// stating when it was measured and that the refresh failed, plus a retry in the parent."
export const StaleAfterFailedRefresh: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1842',
    secondaryLine: 'Measured 2 hours ago — refresh failed',
  },
}

// §StatValue "hover — none on the value... focus-visible — none unless the value is a link...
// active — none... disabled — none. A number is never dimmed to mean 'not applicable'."
export const HoverFocusActiveDisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A value has no hover, active or disabled rendering of its own — a number is never dimmed to
        mean "not applicable"; where it does not apply, the `empty` state below renders instead.
        Focus-visible applies only when the value is itself a link, in which case the standard ring
        applies to the link and never crops the digits.
      </p>
      <StatValue variant="hero" label="1v1 Random Map" value="1842" />
    </div>
  ),
}

export const StackedAlignment: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      <StatValue variant="hero" label="1v1 Random Map" value="1842" />
      <StatValue variant="hero" label="Team Random Map" value="128" />
      <StatValue variant="hero" label="4v4 Random Map" value="15" />
    </div>
  ),
}
