import type { Meta, StoryObj } from '@storybook/react-vite'
import { MatchList, MatchRow } from './index'
import type { MatchRowData } from './index'

const meta: Meta<typeof MatchRow> = {
  title: 'Composite/MatchRow',
  component: MatchRow,
}

export default meta
type Story = StoryObj<typeof MatchRow>

const HOUR_MS = 60 * 60_000
const DAY_MS = 24 * HOUR_MS

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

const base: MatchRowData = {
  gameId: '1001',
  href: '/matches/1001',
  outcome: 'win',
  opponent: { alias: 'aoe2villain' },
  map: 'Arabia',
  civilisation: 'Franks',
  ratingChange: { value: 12 },
  durationLabel: '34 min',
  playedAtRelative: '3 hours ago',
  playedAtAbsolute: '2026-08-22T09:12:00Z',
  captureStatus: 'stored',
  captureDeadlineAt: null,
}

export const Win: Story = {
  args: { match: base },
}

export const Loss: Story = {
  args: {
    match: {
      ...base,
      gameId: '1002',
      outcome: 'loss',
      ratingChange: { value: -8 },
      captureStatus: 'pending',
      captureDeadlineAt: inFromNow(6 * DAY_MS),
    },
  },
}

// match-history.md §2a: `match_players.result` not yet recorded — "Unknown", `text-secondary`,
// never coloured `success`/`danger` and never read as "Loss". No rating change either: a change is
// derived from the same result this ingestion stage has not recorded yet.
export const UnknownOutcome: Story = {
  name: 'Unknown outcome — never rendered as a loss (§2a)',
  args: {
    match: { ...base, gameId: '1009', outcome: 'unknown', ratingChange: undefined },
  },
}

// §4: a team match names the first opposing-team participant and appends "and N others", never a
// bare count and never every alias crammed onto the row.
export const TeamMatchWithOthers: Story = {
  args: {
    match: {
      ...base,
      gameId: '1003',
      opponent: { alias: 'aoe2villain', othersCount: 3 },
    },
  },
}

export const NoRatingChangeRecorded: Story = {
  args: {
    match: { ...base, gameId: '1004', ratingChange: undefined },
  },
}

export const CaptureStillCatchable: Story = {
  args: {
    match: {
      ...base,
      gameId: '1005',
      captureStatus: 'pending',
      captureDeadlineAt: inFromNow(18 * HOUR_MS),
    },
  },
}

export const CaptureLost: Story = {
  args: {
    match: { ...base, gameId: '1006', captureStatus: 'expired' },
  },
}

export const CaptureNeedsReview: Story = {
  args: {
    match: { ...base, gameId: '1007', captureStatus: 'quarantined' },
  },
}

export const CaptureNotDiscoveredYet: Story = {
  name: 'Capture — no ReplayCapture row yet (badge absent, not guessed)',
  args: {
    match: { ...base, gameId: '1008', captureStatus: null },
  },
}

// --- MatchList: the list-level states (§5) — loading, error, empty, and a populated list showing
// all four capture states so the acceptance criterion ("every row shows one of exactly four
// labels") is visible in one screenshot.

const populated: MatchRowData[] = [
  base,
  {
    ...base,
    gameId: '2002',
    outcome: 'loss',
    opponent: { alias: 'aoe2villain', othersCount: 3 },
    ratingChange: { value: -8 },
    captureStatus: 'pending',
    captureDeadlineAt: inFromNow(6 * DAY_MS),
  },
  { ...base, gameId: '2003', captureStatus: 'unavailable', ratingChange: { value: 6 } },
  { ...base, gameId: '2004', captureStatus: 'quarantined', ratingChange: { value: -3 } },
]

export const ListPopulated: Story = {
  name: 'MatchList — populated (all four capture states across rows)',
  render: () => <MatchList matches={populated} />,
}

export const ListLoading: Story = {
  name: 'MatchList — loading (5 skeleton rows, no row count reflow against the populated story)',
  render: () => <MatchList status="loading" />,
}

export const ListError: Story = {
  name: 'MatchList — error, danger callout with retry',
  render: () => <MatchList status="error" matches={populated} onRetry={() => {}} />,
}

export const ListEmpty: Story = {
  name: 'MatchList — empty, "No matches yet"',
  render: () => <MatchList status="empty" />,
}

// §2a's own reproduction: the production page this fix responds to showed eight participants, all
// with `result: null`, as eight losses. This is the same gap at the list level — every row's own
// outcome unrecorded — and every row here MUST read "Unknown", never "Loss".
const allUnknown: MatchRowData[] = populated.map((match, index) => ({
  ...match,
  gameId: `3-${index}`,
  outcome: 'unknown',
  ratingChange: undefined,
}))

export const ListAllOutcomesUnknown: Story = {
  name: 'MatchList — every outcome unknown (the production reproduction, §2a)',
  render: () => <MatchList matches={allUnknown} />,
}

// §11.3 (003, US2): `players.$profileId.matches.tsx` (T331) renders this same component with
// `subject="other"` — the caption and empty-state sentence change, the row never does. Kept beside
// the `subject="self"` stories above so a visual diff catches either drifting from the other
// (§11.6's own "confirmed side by side with that story").
export const ListOtherSubjectPopulated: Story = {
  name: 'MatchList — subject="other", populated ("<alias>\'s recent matches")',
  render: () => <MatchList matches={populated} subject="other" subjectAlias="aoe2villain" />,
}

export const ListOtherSubjectEmpty: Story = {
  name: 'MatchList — subject="other", empty ("<alias> has no matches in their history yet.")',
  render: () => <MatchList status="empty" subject="other" subjectAlias="aoe2villain" />,
}
