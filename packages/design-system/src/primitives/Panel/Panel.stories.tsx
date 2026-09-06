import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { Skeleton } from '../Skeleton'
import { Panel } from './index'

const meta: Meta<typeof Panel> = {
  title: 'Primitives/Panel',
  component: Panel,
  args: {
    density: 'dense',
    heading: 'Recent matches',
  },
}

export default meta
type Story = StoryObj<typeof Panel>

export const Dense: Story = {
  render: (args) => <Panel {...args}>Three matches this week.</Panel>,
}

export const Prose: Story = {
  args: {
    density: 'prose',
    heading: 'What we collect',
  },
  render: (args) => (
    <Panel {...args}>
      A prose panel bounds its text to the reading measure at every width, so it never fills a wide
      page with a single 200-character line even though the panel itself is as wide as its column.
    </Panel>
  ),
}

export const DenseAndProseCompared: Story = {
  // Visual acceptance criterion (structural-tier.md §7): a dense panel and a prose panel in one
  // frame show visibly different distances from their border to their first line of text, and the
  // prose panel's line length is visibly shorter than the page's full column.
  render: () => (
    <div className="flex max-w-page flex-col gap-8">
      <Panel density="dense" heading="Dense">
        Three matches this week.
      </Panel>
      <Panel density="prose" heading="Prose">
        A prose panel bounds its text to the reading measure at every width, so it never fills a
        wide page with a single 200-character line even though the panel itself is as wide as its
        column.
      </Panel>
    </div>
  ),
}

export const NoHeading: Story = {
  render: () => <Panel density="dense">A panel with no header renders a plain div.</Panel>,
}

export const WithDescription: Story = {
  args: {
    description: 'Every match this profile has played, most recent first.',
  },
  render: (args) => <Panel {...args}>Three matches this week.</Panel>,
}

export const WithActions: Story = {
  args: {
    actions: (
      <Button variant="secondary" size="md">
        Export
      </Button>
    ),
  },
  render: (args) => <Panel {...args}>Three matches this week.</Panel>,
}

export const WithFooter: Story = {
  args: {
    footer: <span className="type-supporting text-sm text-text-secondary">3 of 12 shown</span>,
  },
  render: (args) => <Panel {...args}>Three matches this week.</Panel>,
}

export const Loading: Story = {
  args: {
    loading: true,
  },
  render: (args) => (
    <Panel {...args}>
      <Skeleton variant="text" lines={3} />
    </Panel>
  ),
}

export const Empty: Story = {
  // Stands in for `EmptyState` (T548, not yet built): the frame is retained and the body carries
  // the explanation in words, because the caller supplied an empty *condition*, not nothing at
  // all.
  render: (args) => (
    <Panel {...args}>
      <p className="type-body text-md text-text-secondary">
        No matches yet. Play a ranked match to see it here.
      </p>
    </Panel>
  ),
}

export const ErrorStory: Story = {
  name: 'Error',
  // Stands in for `ErrorState` (T548, not yet built): the frame is retained, never removed on
  // failure, so the reader does not lose their place on the page.
  render: (args) => (
    <Panel {...args}>
      <p className="type-body text-md text-text-secondary">
        Match history could not be loaded. Try again.
      </p>
    </Panel>
  ),
}

export const NoChildren: Story = {
  // The other half of the empty state (structural-tier.md §7): a panel given no children at all
  // renders nothing — no frame, no padding. Rendered beside a labelled marker so the absence is
  // visible in the frame rather than reading as an accident of the story.
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Nothing renders below this line:
      </p>
      <Panel density="dense" heading="Never shown" />
    </div>
  ),
}

export const Nested: Story = {
  // The one nesting rule (structural-tier.md §7): the outer panel draws `surface`, the inner one
  // `surface-raised`, and the two must read as distinguishable surfaces in both themes.
  render: () => (
    <Panel density="dense" heading="Match detail">
      <p className="type-body text-md text-text-secondary">Great Palisade Wall, 34 minutes.</p>
      <Panel density="dense" heading="Player 1">
        18 villagers, 4 military units lost.
      </Panel>
    </Panel>
  ),
}
