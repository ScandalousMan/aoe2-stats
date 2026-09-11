import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { Button } from '../Button'
import { Page } from '../Page'
import { Skeleton } from '../Skeleton'
import { StatValue } from '../StatValue'
import { Section } from './index'

const meta: Meta<typeof Section> = {
  id: 'primitives-section',
  title: 'Primitives/Layout & structure/Section',
  component: Section,
  parameters: {
    docs: {
      description: {
        component: `Groups one idea's worth of a page under a heading and owns the space between the components inside it.`,
      },
    },
  },
  args: {
    heading: 'Recent matches',
  },
}

export default meta
type Story = StoryObj<typeof Section>

export const Default: Story = {
  render: (args) => <Section {...args}>Three matches this week.</Section>,
}

export const WithDescription: Story = {
  args: {
    description: 'Every match this profile has played, most recent first.',
  },
  render: (args) => <Section {...args}>Three matches this week.</Section>,
}

export const WithActions: Story = {
  args: {
    actions: (
      <Button variant="secondary" size="md">
        Export
      </Button>
    ),
  },
  render: (args) => <Section {...args}>Three matches this week.</Section>,
}

export const HeadingHidden: Story = {
  args: {
    headingHidden: true,
  },
  render: (args) => (
    <Section {...args}>
      The heading above is present for a screen-reader user and absent from the picture — this story
      stands in for a section whose heading would be visual noise beside a large visible element.
    </Section>
  ),
}

// `Skeleton` stays invisible for the first `duration.normal` (200ms, `useDelayedVisible`) so a
// fast-resolving load never flashes a pulse — a `setTimeout`, not a wall clock, but a clock all
// the same (T568, FR-047). Waiting here for the pulse to exist, rather than screenshotting
// whatever frame Storybook happened to reach first, is what makes this baseline the same no
// matter how long mounting this particular story took.
export const Loading: Story = {
  args: {
    loading: true,
  },
  render: (args) => (
    <Section {...args}>
      <Skeleton variant="text" lines={3} />
      <Skeleton variant="block" className="h-24 w-full" />
    </Section>
  ),
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

export const Empty: Story = {
  // Stands in for `EmptyState` (T548, not yet built): the heading is retained and the body
  // explains why the region is empty, in words, rather than showing a blank box.
  render: (args) => (
    <Section {...args}>
      <p className="type-body text-md text-text-secondary">
        No matches yet. Play a ranked match to see it here.
      </p>
    </Section>
  ),
}

export const ErrorStory: Story = {
  name: 'Error',
  // Stands in for `ErrorState` (T548, not yet built): the heading is retained and the body is
  // replaced entirely — no stale content sits underneath a failed section.
  render: (args) => (
    <Section {...args}>
      <p className="type-body text-md text-text-secondary">
        Match history could not be loaded. Try again.
      </p>
    </Section>
  ),
}

// The nested-section story (structural-tier.md §6): exactly two heading sizes below the page
// title, and the inner one is the smaller. A third level is forbidden and throws instead of
// rendering a heading nothing chose.
export const Nested: Story = {
  render: () => (
    <Section heading="This week">
      <p className="type-body text-md text-text-secondary">Three matches.</p>
      <Section heading="Filters">
        <p className="type-body text-md text-text-secondary">Ranked 1v1 only.</p>
      </Section>
    </Section>
  ),
}

// structural-tier.md §6 "hover / active / focus-visible — none of its own. Its heading is not a
// control and the section is not focusable; the components inside it carry their own."
export const HoverActiveFocusVisibleNotApplicable: Story = {
  render: (args) => (
    <Section {...args}>
      <p className="type-supporting text-sm text-text-secondary">
        A section's heading is not a control and the section itself is not focusable — no hover,
        active or focus-visible rendering of its own. The components inside it carry their own.
      </p>
    </Section>
  ),
}

// §6 "disabled — never. A section the reader may not act on keeps its heading and explains itself
// in words; greying out a whole region tells the reader nothing about why."
export const DisabledNotApplicable: Story = {
  render: (args) => (
    <Section {...args}>
      <p className="type-supporting text-sm text-text-secondary">
        A section is never disabled — a region the reader may not act on keeps its heading and
        explains itself in words instead of greying out.
      </p>
    </Section>
  ),
}

// Composed inside `Page` (structural-tier.md §6, acceptance criteria): the gap between the last
// element of the first section and the heading of the second must read visibly larger than the
// gap between two components inside either section — `Page` owns that between-sections gap,
// `Section` owns the between-components gap inside itself, and this story is where the two are
// seen together.
export const TwoSectionsInPage: Story = {
  render: () => (
    <Page title="Match history" description="Two sections, so the rhythm difference is visible.">
      <Section heading="This week">
        <p className="type-body text-md text-text-secondary">Three matches.</p>
        <p className="type-body text-md text-text-secondary">Two of them ranked.</p>
      </Section>
      <Section heading="Favourites">
        <p className="type-body text-md text-text-secondary">Two profiles.</p>
      </Section>
    </Page>
  ),
  parameters: {
    layout: 'fullscreen',
  },
}

// A realistic combined story: the shape a ratings summary section actually holds — a real
// explanatory sentence and three real `StatValue` leaderboards, at plausible content lengths
// rather than `Three matches.`'s one-line specimens.
export const RealisticRatingsSummary: Story = {
  name: 'Realistic composition — a ratings summary section',
  render: () => (
    <Section
      heading="Your ratings"
      description="Measured after your most recent match on each leaderboard."
    >
      <div className="flex flex-col gap-3">
        <StatValue
          variant="hero"
          label="1v1 Random Map"
          value="1842"
          delta={{ value: 12 }}
          secondaryLine="Measured 3 minutes ago"
        />
        <StatValue variant="hero" label="Team Random Map" value="1690" delta={{ value: -8 }} />
        <StatValue variant="hero" label="4v4 Random Map" value="1512" delta={{ value: 4 }} />
      </div>
    </Section>
  ),
}
