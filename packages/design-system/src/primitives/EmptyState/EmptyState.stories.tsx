import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { EmptyState } from './index'

const meta: Meta<typeof EmptyState> = {
  id: 'primitives-emptystate',
  title: 'Primitives/Feedback & status/EmptyState',
  component: EmptyState,
  args: {
    heading: 'No matches yet',
    explanation:
      'This profile has not played a ranked match since it was linked. New matches appear here automatically.',
  },
}

export default meta
type Story = StoryObj<typeof EmptyState>

export const Default: Story = {}

export const WithAction: Story = {
  args: {
    heading: 'No favourites yet',
    explanation: 'Add a profile from search or a match to keep it one tap away.',
    action: (
      <Button variant="secondary" href="/search">
        Search for a profile
      </Button>
    ),
  },
}

// The two must be unmistakably different, side by side, at a glance (structural-tier.md §12): one
// is words, the other has no text at all.
export const BesideALoadingRegion: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-8">
      <div>
        <p className="mb-2 font-sans text-xs text-text-secondary">Loading (Skeleton, no words)</p>
        <div className="flex flex-col gap-2" aria-busy="true">
          <div className="h-4 w-3/4 animate-pulse rounded-control bg-surface-sunken" />
          <div className="h-4 w-1/2 animate-pulse rounded-control bg-surface-sunken" />
        </div>
      </div>
      <div>
        <p className="mb-2 font-sans text-xs text-text-secondary">Settled and empty (EmptyState)</p>
        <EmptyState heading="No matches yet" explanation="Nothing has been recorded so far." />
      </div>
    </div>
  ),
}

// The caller defect this component exists to make impossible to ship silently: with neither a
// heading nor an explanation, nothing renders at all — never a padded, bordered, wordless box.
export const NoContentRendersNothing: Story = {
  render: () => (
    <div>
      <p className="mb-2 font-sans text-xs text-text-secondary">Nothing renders below this line.</p>
      <EmptyState heading="" explanation="" />
    </div>
  ),
}

// structural-tier.md §12 "hover / focus-visible / active — none of its own; the action inside it
// carries `Button`'s."
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        An empty state has no hover, focus or active rendering of its own — the action inside it,
        when there is one, carries `Button`'s.
      </p>
      <EmptyState {...args} />
    </div>
  ),
}

// §12 "disabled — never. An empty state that cannot be acted on is an empty state with no action
// prop, not a greyed-out one."
export const DisabledNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        An empty state is never disabled — one that cannot be acted on simply omits the `action`
        prop rather than showing a greyed-out one.
      </p>
      <EmptyState {...args} />
    </div>
  ),
}

// §12 "error — not applicable. A region that failed renders `ErrorState`, never 'no results'.
// 'Nothing here' and 'we could not find out' are different facts."
export const ErrorNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A region that failed renders `ErrorState`, never this component — "nothing here" and "we could
      not find out" are different facts a reader acts on differently.
    </p>
  ),
}
