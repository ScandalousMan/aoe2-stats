import type { Meta, StoryObj } from '@storybook/react-vite'
import { MatchList, MatchRow } from './index'
import type { MatchRowData, MatchRowParticipant } from './index'

const meta: Meta<typeof MatchRow> = {
  title: 'Composite/MatchRow',
  component: MatchRow,
}

export default meta
type Story = StoryObj<typeof MatchRow>

// Deadlines are computed relative to render time, not a fixed date, so the countdown text stays
// the same no matter which day this story is captured. `Date.now` is frozen for the whole iframe
// — the same technique `CaptureStateBadge.stories.tsx` uses and explains: `MatchRow` renders
// `CaptureStateBadge` internally, whose own clock (`useTickingNow`) reads `Date.now()`
// independently of the read below, and an unfrozen clock lets those two reads land on either side
// of an exact-unit boundary, flipping the rendered text between runs (T505's identity proof).
const FROZEN_NOW_MS = Date.parse('2026-01-01T00:00:00.000Z')
Date.now = () => FROZEN_NOW_MS

const HOUR_MS = 60 * 60_000
const DAY_MS = 24 * HOUR_MS

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

const BRITONS_URL = '/game-assets/civilisations/britons.webp'
const ARABIA_URL = '/game-assets/maps/arabia.webp'

// §12.3: a 1v1 is two groups of one — the viewed profile's group first (`isViewer`), "vs", then
// the opponent's group.
const participants1v1Win: MatchRowParticipant[] = [
  { profileId: 1807091, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
  { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'loss' },
]

const participants1v1Loss: MatchRowParticipant[] = [
  { profileId: 1807091, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'loss', isViewer: true },
  { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'win' },
]

const base: MatchRowData = {
  gameId: '1001',
  href: '/matches/1001',
  outcome: 'win',
  participants: participants1v1Win,
  map: 'Arabia',
  civilisation: 'Britons',
  civIconUrl: BRITONS_URL,
  mapThumbnailUrl: ARABIA_URL,
  leaderboardName: '1v1 Random Map',
  rating: 922,
  ratingChange: { value: 16 },
  durationLabel: '34 min',
  playedAtRelative: '3 hours ago',
  playedAtAbsolute: '2026-08-22T09:12:00Z',
  captureStatus: 'stored',
  captureDeadlineAt: null,
}

// §12.4: the FR-005 case exactly as the spec's own example — "922 (+16)".
export const Win: Story = {
  name: '1v1, a win (§12.3 two groups + §12.4 rating format)',
  args: { match: base },
}

export const Loss: Story = {
  args: {
    match: {
      ...base,
      gameId: '1002',
      outcome: 'loss',
      participants: participants1v1Loss,
      rating: 906,
      ratingChange: { value: -15 },
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
    match: {
      ...base,
      gameId: '1009',
      outcome: 'unknown',
      rating: undefined,
      ratingChange: undefined,
      participants: participants1v1Win.map((participant) => ({ ...participant, result: null })),
    },
  },
}

export const NoRatingChangeRecorded: Story = {
  args: {
    match: { ...base, gameId: '1004', rating: undefined, ratingChange: undefined },
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

// --- §12: the four scenarios T430 exists to cover -----------------------------------------------

// §12.3's "Two groups" cap-of-three row: a 4v4 (eight players), one side already Won, the other
// side's results not yet recorded — demonstrating both the overflow ("and 1 other") and the
// three-state `TeamResult` marker's neutral case in one frame.
const eightPlayerParticipants: MatchRowParticipant[] = [
  { profileId: 1807091, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
  { profileId: 2, alias: 'RedTeammate', teamId: 1, colorId: 2, result: 'win' },
  { profileId: 3, alias: 'GreenTeammate', teamId: 1, colorId: 3, result: 'win' },
  { profileId: 4, alias: 'TealTeammate', teamId: 1, colorId: 5, result: 'win' },
  { profileId: 5, alias: 'aoe2villain', teamId: 2, colorId: 6, result: null },
  { profileId: 6, alias: 'PurpleRival', teamId: 2, colorId: 7, result: null },
  { profileId: 7, alias: 'GreyRival', teamId: 2, colorId: 8, result: null },
  { profileId: 8, alias: 'OrangeRival', teamId: 2, colorId: 1, result: null },
]

export const EightPlayerMatch: Story = {
  name: 'Eight-player match (4v4) — cap of three per side, "and 1 other" (§12.3, §12.8)',
  args: {
    match: {
      ...base,
      gameId: '2001',
      participants: eightPlayerParticipants,
    },
  },
}

// §12.6: every participant column NULL (the un-projected row — "the state every production row
// is in until the backfill runs"). Map, ladder, duration, when and the capture badge still
// render; `Outcome` reads "Unknown"; `Participants` is **omitted entirely** — no empty "vs".
export const NullResult: Story = {
  name: 'A null result — the un-projected row, Participants omitted entirely (§12.6)',
  args: {
    match: {
      ...base,
      gameId: '3001',
      outcome: 'unknown',
      participants: undefined,
      civIconUrl: undefined,
      mapThumbnailUrl: undefined,
      rating: undefined,
      ratingChange: undefined,
    },
  },
}

// §12.1 rule 3: the absent-asset state is the prop being `undefined` — no box, no silhouette, no
// "?" tile. Every mark this row can carry is uncovered at once: the civilisation icon, the map
// thumbnail, and every participant's colour.
const uncoveredParticipants: MatchRowParticipant[] = participants1v1Win.map((participant) => ({
  ...participant,
  colorId: null,
}))

export const NoAssetsCovered: Story = {
  name: 'No assets covered — unknown civ, unknown map, no colour (§12.1 rule 3, §12.8)',
  args: {
    match: {
      ...base,
      gameId: '4001',
      civilisation: 'Gurjaras',
      civIconUrl: undefined,
      map: 'A Custom Tournament Map',
      mapThumbnailUrl: undefined,
      participants: uncoveredParticipants,
    },
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
    participants: participants1v1Loss,
    rating: 906,
    ratingChange: { value: -15 },
    captureStatus: 'pending',
    captureDeadlineAt: inFromNow(6 * DAY_MS),
  },
  {
    ...base,
    gameId: '2003',
    captureStatus: 'unavailable',
    rating: 928,
    ratingChange: { value: 6 },
  },
  {
    ...base,
    gameId: '2004',
    captureStatus: 'quarantined',
    rating: 919,
    ratingChange: { value: -3 },
  },
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
  rating: undefined,
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
