import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { EmptyState } from '../EmptyState'
import { ErrorState } from '../ErrorState'
import { Table, type TableColumn } from './index'

// packages/design-system/specs/structural-tier.md §10: the caption and the column headers stay,
// and the body becomes one cell spanning every column, holding one `ErrorState` (with a retry) or
// one `EmptyState` (with its sentence) — never a bare header over nothing.

interface MatchRow {
  gameId: string
  opponent: string
  rating: number
  ratingChange: number
  durationMinutes: number
  when: string
}

const matches: MatchRow[] = [
  {
    gameId: 'g-1',
    opponent: 'RedBull_Barley',
    rating: 1876,
    ratingChange: 24,
    durationMinutes: 34,
    when: '3 hours ago',
  },
  {
    gameId: 'g-2',
    opponent: 'Yo',
    rating: 1852,
    ratingChange: -12,
    durationMinutes: 8,
    when: 'yesterday',
  },
  {
    gameId: 'g-3',
    opponent: 'TheViper_fan99',
    rating: 1864,
    ratingChange: 156,
    durationMinutes: 61,
    when: '2 days ago',
  },
]

// Every digit count a real column shows: single, double and triple-digit deltas, so the alignment
// acceptance criterion (structural-tier.md §10, SC-009) is visible in one story rather than
// asserted only by the interaction test that swaps the monospace family.
const columns: [TableColumn<MatchRow>, ...TableColumn<MatchRow>[]] = [
  { key: 'opponent', header: 'Opponent', render: (row) => row.opponent },
  { key: 'rating', header: 'Rating', align: 'numeric', render: (row) => row.rating },
  {
    key: 'ratingChange',
    header: 'Change',
    align: 'numeric',
    render: (row) => (row.ratingChange >= 0 ? `+${row.ratingChange}` : String(row.ratingChange)),
  },
  {
    key: 'duration',
    header: 'Duration',
    align: 'numeric',
    render: (row) => `${row.durationMinutes} min`,
  },
  { key: 'when', header: 'When', render: (row) => row.when },
]

const meta: Meta<typeof Table<MatchRow>> = {
  title: 'Primitives/Table',
  component: Table,
}

export default meta
type Story = StoryObj<typeof Table<MatchRow>>

export const Default: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
    />
  ),
}

// structural-tier.md §10 "hover"/"active": a row highlights only when the whole row is a real
// link. Both a linked and a non-linked row sit in the same table so the difference is visible.
export const RowLinks: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
      getRowHref={(row) => (row.gameId === 'g-2' ? undefined : `/matches/${row.gameId}`)}
    />
  ),
}

export const CaptionHidden: Story = {
  render: () => (
    <div>
      <h2 className="type-display mb-2 text-xl font-semibold text-text-primary">Recent matches</h2>
      <Table
        caption="Recent matches"
        captionHidden
        columns={columns}
        rows={matches}
        getRowKey={(row) => row.gameId}
      />
    </div>
  ),
}

export const Loading: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={[]}
      getRowKey={(row) => row.gameId}
      status="loading"
      skeletonRowCount={4}
    />
  ),
}

export const ErrorStatus: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={[]}
      getRowKey={(row) => row.gameId}
      status="error"
      errorContent={
        <ErrorState
          heading="Matches could not load"
          explanation="Something went wrong fetching this profile's matches."
          action={
            <Button variant="secondary" size="md">
              Retry
            </Button>
          }
        />
      }
    />
  ),
}

export const Empty: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={[]}
      getRowKey={(row) => row.gameId}
      status="empty"
      emptyContent={
        <EmptyState
          heading="No matches yet"
          explanation="This profile has not played a captured match."
        />
      }
    />
  ),
}

export const WithFooter: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
      footer={`${matches.length} matches shown`}
    />
  ),
}

// structural-tier.md §3: `prose` reads `type-body` at `text-md` and pads rows at `space-4`,
// visibly taller than `dense`'s `space-3`/`text-sm` — a `dense` and a `prose` table side by side
// have visibly different row heights (§10's own acceptance criterion).
export const ProseDensity: Story = {
  render: () => (
    <Table
      caption="Terms used on this page"
      density="prose"
      columns={[
        { key: 'term', header: 'Term', render: (row) => row.term },
        { key: 'meaning', header: 'Meaning', render: (row) => row.meaning },
      ]}
      rows={[
        { term: 'Objection', meaning: 'A request to stop further capture of your recordings.' },
        { term: 'Erasure', meaning: 'A request to remove your link to a captured match.' },
      ]}
      getRowKey={(row) => row.term}
    />
  ),
}

export const DenseAndProseCompared: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <Table
        caption="Recent matches (dense)"
        columns={columns}
        rows={matches.slice(0, 2)}
        getRowKey={(row) => row.gameId}
      />
      <Table
        caption="Terms used on this page (prose)"
        density="prose"
        columns={[
          { key: 'term', header: 'Term', render: (row) => row.term },
          { key: 'meaning', header: 'Meaning', render: (row) => row.meaning },
        ]}
        rows={[{ term: 'Objection', meaning: 'A request to stop further capture.' }]}
        getRowKey={(row) => row.term}
      />
    </div>
  ),
}

// structural-tier.md §10 "Overflow": more columns than a narrow container can show at once. The
// wrapping `div` below stands in for a caller's own narrow layout; at 375 the frame stays fully
// inside the page padding and only the table's own region scrolls (FR-026, FR-018) — the table is
// never what makes the page scroll sideways.
const wideColumns: [TableColumn<MatchRow>, ...TableColumn<MatchRow>[]] = [
  ...columns,
  { key: 'gameId', header: 'Match id', render: (row) => row.gameId },
  {
    key: 'note',
    header: 'Note',
    render: () => 'A long note column, wide enough on its own to force this table to overflow.',
  },
]

export const Overflow: Story = {
  render: () => (
    <div className="max-w-sm">
      <Table
        caption="Recent matches"
        columns={wideColumns}
        rows={matches}
        getRowKey={(row) => row.gameId}
      />
    </div>
  ),
}
