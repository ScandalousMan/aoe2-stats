import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReactNode } from 'react'
import { expect, waitFor, within } from 'storybook/test'
import { Button } from '../Button'
import { EmptyState } from '../EmptyState'
import { ErrorState } from '../ErrorState'
import { Skeleton } from '../Skeleton'
import { MatchList } from '../../composites/MatchRow'
import type { MatchRowData } from '../../composites/MatchRow'
import { Page } from './index'

const meta: Meta<typeof Page> = {
  id: 'primitives-page',
  title: 'Primitives/Layout & structure/Page',
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

// `Skeleton` stays invisible for the first `duration.normal` (200ms, `useDelayedVisible`) so a
// fast-resolving load never flashes a pulse — a `setTimeout`, not a wall clock, but a clock all
// the same (T568, FR-047). Waiting here for the pulse to exist, rather than screenshotting
// whatever frame Storybook happened to reach first, is what makes this baseline the same no
// matter how long mounting this particular story took.
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
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
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

// structural-tier.md §5 "error — the header is retained and the section stack is replaced by one
// `ErrorState`. Retaining the header is what keeps a failed route from looking like the wrong
// route."
export const Error: Story = {
  render: (args) => (
    <Page {...args}>
      <ErrorState
        heading="We could not load this match history"
        explanation="Something went wrong on our end. Try again in a moment."
        action={<Button variant="secondary">Try again</Button>}
      />
    </Page>
  ),
}

// §5 "empty — a `Page` with a header and no sections renders the header plus one `EmptyState`. A
// padded, bordered, wordless column is the defect FR-023 names."
export const Empty: Story = {
  render: (args) => (
    <Page {...args}>
      <EmptyState
        heading="No matches yet"
        explanation="Matches this profile plays online will appear here automatically."
      />
    </Page>
  ),
}

// §5 "focus-visible — the landmark is the skip link's target and carries `tabIndex={-1}`. When
// the skip link sends focus to it, it shows the standard ring... It never shows a ring on a
// pointer click." Forced here by focusing the `<main>` landmark directly, the same route a real
// skip link takes.
export const FocusVisible: Story = {
  render: (args) => (
    <Page {...args}>
      <SamplePanel title="Recent matches">Three matches this week.</SamplePanel>
    </Page>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    canvas.getByRole('main').focus()
  },
}

// §5 "hover / active — none. A page is not a control." / "disabled — never. A page cannot be
// disabled; a route the reader may not use renders an `ErrorState` (§13) explaining why, inside a
// normal `Page`."
export const HoverActiveDisabledNotApplicable: Story = {
  render: (args) => (
    <Page {...args}>
      <p className="type-supporting text-sm text-text-secondary">
        A page is not a control: no hover and no active state. It cannot be disabled either — a
        route the reader may not use renders an `ErrorState` explaining why, inside a normal page,
        rather than a disabled one.
      </p>
    </Page>
  ),
}

// A realistic combined story: the shape `MatchHistoryContainer.tsx` (apps/web) actually renders —
// a hidden title (the page header lives in `ProfileSummary/compact` instead) above a real
// `MatchList`, at plausible content lengths rather than `SamplePanel`'s one-line specimens.
const realisticMatches: MatchRowData[] = [
  {
    gameId: '1001',
    href: '/matches/1001',
    outcome: 'win',
    participants: [
      {
        profileId: 1807091,
        alias: 'GL.TheViper',
        teamId: 1,
        colorId: 4,
        result: 'win',
        isViewer: true,
      },
      { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'loss' },
    ],
    map: 'Arabia',
    civilisation: 'Britons',
    civIconUrl: '/game-assets/civilisations/britons.webp',
    mapThumbnailUrl: '/game-assets/maps/arabia.webp',
    leaderboardName: '1v1 Random Map',
    rating: 1842,
    ratingChange: { value: 16 },
    durationLabel: '34 min',
    playedAtRelative: '3 hours ago',
    playedAtAbsolute: '2026-08-22T09:12:00Z',
    captureStatus: 'stored',
    captureDeadlineAt: null,
  },
  {
    gameId: '1002',
    href: '/matches/1002',
    outcome: 'loss',
    participants: [
      {
        profileId: 1807091,
        alias: 'GL.TheViper',
        teamId: 1,
        colorId: 4,
        result: 'loss',
        isViewer: true,
      },
      { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'win' },
    ],
    map: 'Black Forest',
    civilisation: 'Mayans',
    civIconUrl: '/game-assets/civilisations/mayans.webp',
    mapThumbnailUrl: '/game-assets/maps/black_forest.webp',
    leaderboardName: '1v1 Random Map',
    rating: 1826,
    ratingChange: { value: -16 },
    durationLabel: '52 min',
    playedAtRelative: 'yesterday',
    playedAtAbsolute: '2026-08-21T18:03:00Z',
    captureStatus: 'pending',
    captureDeadlineAt: null,
  },
]

export const RealisticMatchHistory: Story = {
  name: 'Realistic composition — MatchHistoryContainer (title hidden, real MatchList)',
  args: { title: 'Match history', titleHidden: true },
  render: (args) => (
    <Page {...args}>
      <MatchList matches={realisticMatches} />
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
