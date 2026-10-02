import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
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
  id: 'primitives-table',
  title: 'Primitives/Layout & structure/Table',
  component: Table,
  parameters: {
    docs: {
      description: {
        component: `Lets a reader compare rows of measured values by eye, quickly, with the digits lined up and nothing decorative between them.`,
      },
    },
  },
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
// link. This story shows the two kinds of row side by side — at rest they are pixel-identical by
// design (`--default` above is the same table with no linked rows at all); `RowLinkHover` below is
// the story that actually demonstrates the difference.
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

// `status="loading"` renders `Skeleton` rows, which stay invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
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
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
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

// `role: 'link', name: 'RedBull_Barley'` is unambiguous: exactly one anchor in this table carries
// that name. Declared here, ahead of every story that clips to it (a module-level `const` is not
// hoisted the way a function declaration is).
const ROW_LINK_CLIP = { parts: [{ role: 'link' as const, name: 'RedBull_Barley' }], pad: '2' }

// The hover fill (`hover:bg-surface-sunken`, index.tsx: painted on the `<tr>` itself) and the
// active fill plus ring (`active:bg-surface-sunken` on the `<tr>`; `active:after:ring-2
// active:after:ring-inset active:after:ring-border-strong` on the stretched link's `::after`,
// which is `after:absolute after:inset-0` against the *row* — the nearest `relative` ancestor,
// since the `<a>` itself is `static`) both paint against the row, not the anchor's own text box.
// `ROW_LINK_CLIP` above locates the `<a>` alone and crops every one of those marks out: a frame
// clipped to it shows only the underline (which *is* on the anchor) and nothing that tells a
// reader the row is filled, that the row rules still show through the fill (§10's own hover
// acceptance criterion), or — for `Active` — that the ring is there at all. `RowLinkActive` below
// therefore clips to the row instead, via a selector rather than `role`/`name` (a `<tr>` carries no
// ARIA role name of its own) — `RowLinkHover` does not: see that story's own comment for why the
// fill it would otherwise show is a fact no frame can make the comparator register at all.
// `RowLinkFocusVisible` further below is the other row-link state in this file whose own mark —
// the `focusRing` outline, painted directly on the anchor and offset only by `outline-offset-ring`'s
// 2px, well inside `pad: '2'`'s 8px — never leaves the anchor's own box, so it too stays on
// `ROW_LINK_CLIP`.
const ROW_LINK_ROW_CLIP = {
  parts: [{ selector: 'tr:has(a[href="/matches/g-1"])' }],
  pad: '2',
}

// structural-tier.md §10 "hover — a row highlights with `surface-sunken` only when the whole row
// is a real link," and its own acceptance criterion: "exactly one row is filled, its identity
// text is underlined (§16.1), and the row rules are still visible through the fill."
// `tests/visual/stories.spec.ts` drives the real `:hover` on the row's own anchor from Playwright
// once this story has settled (see that file's own `VisualForceState` comment) — a `play()` here
// could only dispatch a synthetic event, which the pseudo-class ignores.
//
// T675 remediation (N1, arbitrated by the project owner): this story clips to `ROW_LINK_CLIP` —
// the anchor alone — not the row. Measured at threshold 0.2 in both themes: on the row clip the
// hover underline is 182 differing px, which is 0.25% at 1280, 0.43% at 768 and 0.67% at 375 —
// under the comparator's 1% gate on every unit, and the one mark that story-baselines-duplicates.mjs
// could no longer tell apart from `Active`'s own rest. Clipped instead to the anchor
// (`ROW_LINK_CLIP`, ~114x33px), the same 182px reads ~4.8% on every unit — the underline is the
// only signal the comparator actually registers for this state, at any frame size the gate can
// pass. The fill and the row rules showing through it are real (structural-tier.md §16.1 describes
// them), but they are fill-only facts: a solid colour step the comparator at threshold 0.2 does not
// count as differing pixels at all, on the row clip or any other — no frame, clipped or not, can
// make that part of this state hold the 1% gate, which is why the row frame is not the answer here
// (structural-tier.md §16.1, amended alongside this change to say so). `RowLinkActive` below keeps
// `ROW_LINK_ROW_CLIP`: its own ring is a geometric mark, not a fill, and measures 5.8-7.5% there (nightly run 36903179643).
export const RowLinkHover: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
      getRowHref={(row) => (row.gameId === 'g-2' ? undefined : `/matches/${row.gameId}`)}
    />
  ),
  parameters: {
    visualForceState: { state: 'hover', role: 'link', name: 'RedBull_Barley' },
    visualCaptureClip: ROW_LINK_CLIP,
  },
}

// §10 "active — a row link's press keeps the hover fill and adds a rule down the row's
// inline-start edge, in `border-strong`" (fourth-pass review remediation, FR-037), and its own
// acceptance criterion: the active capture "shows the same underline and, in addition, the full
// inset ring" that the hover capture does not. Held down rather than released so the capture shows
// the pressed frame. The harness presses by a real hover then a mouse-down, so §16.1's underline is
// in this frame too. `ROW_LINK_ROW_CLIP` (declared above `RowLinkHover`) is what makes the ring
// checkable here: the ring is a geometric mark against the row, outside the anchor `ROW_LINK_CLIP`
// alone would crop to, and (unlike the hover fill `RowLinkHover` no longer clips to the row for —
// see that story's own comment) it measures well over the comparator's 1% gate there, 5.8-7.5% on
// every unit.
export const RowLinkActive: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
      getRowHref={(row) => (row.gameId === 'g-2' ? undefined : `/matches/${row.gameId}`)}
    />
  ),
  parameters: {
    visualForceState: { state: 'active', role: 'link', name: 'RedBull_Barley' },
    visualCaptureClip: ROW_LINK_ROW_CLIP,
  },
}

// §10 "focus-visible — the scroll region shows the standard ring when it is focused for
// scrolling; a focusable element inside a cell shows its own ring, offset so the frame does not
// clip it." Shown here on the region itself, named by its own caption (`index.tsx`'s
// `aria-labelledby={captionId}`).
export const FocusVisible: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
    />
  ),
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'region', name: 'Recent matches' },
  },
}

// §10 "focus-visible ... a focusable element inside a cell shows its own ring": the row link's own
// ring (`focusRing`, index.tsx:281-286), real and undepicted until now — `RowLinkHover`/
// `RowLinkActive` above force the other two states on this exact anchor, but no story forced this
// one.
//
// README's gap register row 8 (H5), 8h: this ring paints — `visual-reviewer` confirmed a real,
// token-blue boxed outline around "RedBull_Barley" in every captured frame — the finding that
// `story-baselines-duplicates.mjs` flagged this story as a full-set duplicate of `RowLinks` was a
// framing gap, not a rendering one: an unclipped full-table frame puts the ring's own geometry at
// roughly 0.15-0.47% of the page, under both that checker's `DUPLICATE_MAX_DIFF_RATIO` and
// `playwright.config.ts`'s own `maxDiffPixelRatio` (both 0.01), the same "rule row 3" ceiling every
// other single-control ring in this package clips against (`PrivacyNotice`'s `FIRST_LINK_CLIP`/
// `INLINE_LINK_CLIP`, `AccountErasurePanel`'s `checkboxClip`) — the same `ROW_LINK_CLIP` this story
// clips to, unlike `RowLinkActive` above, which needs the row-level `ROW_LINK_ROW_CLIP` instead
// (its own ring paints against the row): this focus ring, like `RowLinkHover`'s own underline, is a
// mark that paints directly on the anchor and never leaves its box, so the anchor alone is still
// the right frame for it.
export const RowLinkFocusVisible: Story = {
  render: () => (
    <Table
      caption="Recent matches"
      columns={columns}
      rows={matches}
      getRowKey={(row) => row.gameId}
      getRowHref={(row) => (row.gameId === 'g-2' ? undefined : `/matches/${row.gameId}`)}
    />
  ),
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link', name: 'RedBull_Barley' },
    visualCaptureClip: ROW_LINK_CLIP,
  },
}

// §10 "disabled — never. A table whose data is stale says so in a `Callout` above it; a greyed
// table is unreadable and still on screen."
export const DisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A table is never disabled — data that is stale says so in a `Callout` above it, never in a
        greyed-out, still-readable table.
      </p>
      <Table
        caption="Recent matches"
        columns={columns}
        rows={matches}
        getRowKey={(row) => row.gameId}
      />
    </div>
  ),
}
