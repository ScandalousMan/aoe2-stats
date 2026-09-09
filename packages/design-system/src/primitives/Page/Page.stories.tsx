import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReactNode } from 'react'
import { expect, waitFor, within } from 'storybook/test'
import { Button } from '../Button'
import { EmptyState } from '../EmptyState'
import { ErrorState } from '../ErrorState'
import { Panel } from '../Panel'
import { Section } from '../Section'
import { Skeleton } from '../Skeleton'
import { Table, type TableColumn } from '../Table'
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
  // A `play()` calling `.focus()` sets DOM focus but not the `:focus-visible` pseudo-class, so this
  // story captured the same frame as `Default` until the suite forced the state for it — the defect
  // T565's whole sweep shipped and five review rounds kept finding one more instance of. The forced
  // state is the capture; the `play()` below stays because it asserts the landmark is reachable at
  // all, which is a different claim from what the ring looks like.
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'main' },
  },
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

// A realistic combined story: a hidden title (the page header lives in `ProfileSummary/compact`
// instead) above a bounded `Section`/`Panel` holding a `dense` `Table` of plausible match rows —
// the shape `structural-tier.md` §10 names `Table` for (a data-comparison surface), built from
// primitives only. `MatchList` (`composites/MatchRow`) is the domain composite that actually wraps
// this shape in `apps/web`; a primitive story may not import it (FR-029, `tier-deps.mjs`), so this
// story demonstrates the same realistic content lengths — full alias, map and civilisation names,
// double- and triple-digit rating deltas, plausible durations — through `Table` directly, the
// primitive `structural-tier.md` says a domain composite is itself built from.
interface RealisticMatchRow {
  gameId: string
  opponent: string
  map: string
  civilisation: string
  rating: number
  ratingChange: number
  durationLabel: string
  when: string
  captureStatus: string
}

const realisticMatches: RealisticMatchRow[] = [
  {
    gameId: '1001',
    opponent: 'aoe2villain',
    map: 'Arabia',
    civilisation: 'Britons',
    rating: 1842,
    ratingChange: 16,
    durationLabel: '34 min',
    when: '3 hours ago',
    captureStatus: 'Replay stored',
  },
  {
    gameId: '1002',
    opponent: 'aoe2villain',
    map: 'Black Forest',
    civilisation: 'Mayans',
    rating: 1826,
    ratingChange: -16,
    durationLabel: '52 min',
    when: 'yesterday',
    captureStatus: 'Capture pending',
  },
]

const realisticMatchColumns: [TableColumn<RealisticMatchRow>, ...TableColumn<RealisticMatchRow>[]] =
  [
    { key: 'opponent', header: 'Opponent', render: (row) => row.opponent },
    { key: 'civilisation', header: 'Civilisation', render: (row) => row.civilisation },
    { key: 'map', header: 'Map', render: (row) => row.map },
    { key: 'rating', header: 'Rating', align: 'numeric', render: (row) => row.rating },
    {
      key: 'ratingChange',
      header: 'Change',
      align: 'numeric',
      render: (row) => (row.ratingChange >= 0 ? `+${row.ratingChange}` : String(row.ratingChange)),
    },
    { key: 'duration', header: 'Duration', render: (row) => row.durationLabel },
    { key: 'when', header: 'When', render: (row) => row.when },
    { key: 'captureStatus', header: 'Capture', render: (row) => row.captureStatus },
  ]

export const RealisticMatchHistory: Story = {
  name: 'Realistic composition — a dense Table of match rows',
  args: { title: 'Match history', titleHidden: true },
  render: (args) => (
    <Page {...args}>
      <Section heading="Recent matches">
        <Panel density="dense">
          <Table
            // structural-tier.md: a hidden caption must say something the heading above it does
            // not, or the Section landmark and this Table's scroll region collapse to one
            // accessible name (landmark-unique). "Recent matches" duplicated the Section heading
            // above and was caught by CI's axe pass, not by this file's own tests.
            caption="2 most recent matches, newest first"
            captionHidden
            density="dense"
            columns={realisticMatchColumns}
            rows={realisticMatches}
            getRowKey={(row) => row.gameId}
            getRowHref={(row) => `/matches/${row.gameId}`}
          />
        </Panel>
      </Section>
    </Page>
  ),
}

// A deliberately minimal bounded block with a heading — not `Panel` or `Section`, which this file
// imports and uses directly in the realistic-composition stories above. This stand-in exists for
// the stories that only need to show the between-sections rhythm `Page` owns, without pulling in
// either primitive's own surface and heading conventions for a specimen that doesn't need them.
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
