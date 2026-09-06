import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { EmptyState } from './index'

const meta: Meta<typeof EmptyState> = {
  title: 'Primitives/EmptyState',
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
