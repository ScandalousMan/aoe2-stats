import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReactNode } from 'react'
import { Button } from '../Button'
import { Skeleton } from '../Skeleton'
import { Page } from './index'

const meta: Meta<typeof Page> = {
  title: 'Primitives/Page',
  component: Page,
  args: {
    title: 'Match history',
  },
  parameters: {
    // Full-page primitive: the layout, the padding and the landmark are only meaningful at the
    // page's own footprint, not inside Storybook's default padded canvas.
    layout: 'fullscreen',
  },
}

export default meta
type Story = StoryObj<typeof Page>

export const Default: Story = {
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Recent matches">Three matches this week.</SamplePanel>
    </Page>
  ),
}

export const WithDescription: Story = {
  args: {
    description: 'Every match this profile has played, most recent first.',
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Recent matches">Three matches this week.</SamplePanel>
    </Page>
  ),
}

export const WithActions: Story = {
  args: {
    description: 'Every match this profile has played, most recent first.',
    actions: (
      <Button variant="secondary" size="md">
        Export
      </Button>
    ),
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Recent matches">Three matches this week.</SamplePanel>
    </Page>
  ),
}

export const TitleHidden: Story = {
  args: {
    title: 'Match history',
    titleHidden: true,
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Recent matches">
        The title above is present for a screen-reader user and absent from the picture — this story
        stands in for a route whose title is already carried by a large visible element.
      </SamplePanel>
    </Page>
  ),
}

export const WidthPanel: Story = {
  args: {
    title: 'Link another Steam account',
    width: 'panel',
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Search">
        A single-column form or result column, `size.panel` wide.
      </SamplePanel>
    </Page>
  ),
}

export const WidthMeasure: Story = {
  args: {
    title: 'Privacy notice',
    width: 'measure',
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="What we collect">
        Continuous reading content bounded to the reading-measure width, so a route built for prose
        never produces a 200-character line.
      </SamplePanel>
    </Page>
  ),
}

export const Loading: Story = {
  args: {
    title: 'Match history',
    loading: true,
  },
  render: (args) => (
    <Page {...args}>
      <Skeleton variant="text" lines={3} />
      <Skeleton variant="block" className="h-24 w-full" />
    </Page>
  ),
}

export const TwoSections: Story = {
  args: {
    description: 'Two sections, so the between-sections rhythm is visible against the header.',
  },
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="This week">Three matches.</SamplePanel>
      <SamplePanel title="Favourites">Two profiles.</SamplePanel>
    </Page>
  ),
}

// A stand-in for `Panel` (T544, not yet built) and `Section` (T544): a bounded block with a
// heading, just enough to show the between-sections rhythm `Page` owns without depending on a
// primitive this task does not build.
function SamplePanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={`${title.toLowerCase().replace(/\s+/g, '-')}-heading`}
      className="rounded-panel border border-border bg-surface p-4"
    >
      <h2
        id={`${title.toLowerCase().replace(/\s+/g, '-')}-heading`}
        className="type-display text-xl font-semibold text-text-primary"
      >
        {title}
      </h2>
      <p className="type-body text-md mt-2 text-text-secondary">{children}</p>
    </section>
  )
}
