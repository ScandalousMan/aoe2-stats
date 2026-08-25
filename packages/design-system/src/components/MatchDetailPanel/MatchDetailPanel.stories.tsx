import type { Meta, StoryObj } from '@storybook/react-vite'
import { MatchDetailPanel } from './index'
import type { MatchDetailData } from './index'

const meta: Meta<typeof MatchDetailPanel> = {
  title: 'Composite/MatchDetailPanel',
  component: MatchDetailPanel,
}

export default meta
type Story = StoryObj<typeof MatchDetailPanel>

const baseMatch: MatchDetailData = {
  gameId: '1001',
  map: 'Arabia',
  leaderboardName: '1v1 Random Map',
  durationLabel: '34 min',
  playedAtLabel: '22 Aug 2026, 14:32',
  // §11.1 point 3 / §11.6: present in every header story, raw and verbatim — never resolved.
  gameVersion: '101.101',
  captureStatus: 'stored',
  captureDeadlineAt: null,
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'aoe2guy',
          civId: 10,
          civName: 'Franks',
          result: 'win',
          ratingChange: { value: 12 },
        },
      ],
    },
    {
      id: 'team-2',
      name: 'Team 2',
      participants: [
        {
          id: 'p2',
          alias: 'aoe2villain',
          civId: 20,
          civName: 'Mongols',
          result: 'loss',
          ratingChange: { value: -12 },
        },
      ],
    },
  ],
}

const teamMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1002',
  leaderboardName: '2v2 Random Map',
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'aoe2guy',
          civId: 10,
          civName: 'Franks',
          result: 'win',
          ratingChange: { value: 9 },
        },
        {
          id: 'p2',
          alias: 'aoe2friend',
          civId: 5,
          civName: 'Britons',
          result: 'win',
          ratingChange: { value: 9 },
        },
      ],
    },
    {
      id: 'team-2',
      name: 'Team 2',
      participants: [
        {
          id: 'p3',
          alias: 'aoe2villain',
          civId: 20,
          civName: 'Mongols',
          result: 'loss',
          ratingChange: { value: -9 },
        },
        {
          id: 'p4',
          alias: 'aoe2foe',
          civId: 15,
          civName: 'Huns',
          result: 'loss',
          ratingChange: { value: -9 },
        },
      ],
    },
  ],
}

// §11.4: "many participants, still one anatomy" — an eight-player free-for-all is eight
// `TeamGroup`s of one, generalising the same `ParticipantsTable` a 1v1 already uses, with no new
// layout branch.
const eightPlayerFfaMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1006',
  leaderboardName: 'Free-for-All',
  teams: [
    { civId: 10, civName: 'Franks', alias: 'aoe2guy', result: 'win' as const, value: 41 },
    { civId: 20, civName: 'Mongols', alias: 'aoe2villain', result: 'loss' as const, value: -6 },
    { civId: 5, civName: 'Britons', alias: 'aoe2friend', result: 'loss' as const, value: -6 },
    { civId: 15, civName: 'Huns', alias: 'aoe2foe', result: 'loss' as const, value: -6 },
    { civId: 3, civName: 'Aztecs', alias: 'aoe2rando1', result: 'loss' as const, value: -6 },
    { civId: 8, civName: 'Byzantines', alias: 'aoe2rando2', result: 'loss' as const, value: -6 },
    { civId: 1, civName: 'Aztecs', alias: 'aoe2rando3', result: 'loss' as const, value: -6 },
    { civId: 30, civName: 'Mayans', alias: 'aoe2rando4', result: 'loss' as const, value: -5 },
  ].map((p, index) => ({
    id: `team-${index + 1}`,
    name: `Team ${index + 1}`,
    participants: [
      {
        id: `p${index + 1}`,
        alias: p.alias,
        civId: p.civId,
        civName: p.civName,
        result: p.result,
        ratingChange: { value: p.value },
      },
    ],
  })),
}

// §11.2: FR-020, no guess. `Fr020B`'s civilisation is a game-version id this service's reference
// data has never learned, and the header's map carries no name either — placed alongside a fully
// resolved participant so the visual distinction (`text-secondary`/`font-mono` vs
// `text-primary`/`sans`) reads in one frame (§11.6).
const unresolvedIdentifierMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1007',
  map: null,
  gameVersion: '101.102',
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'Fr020A',
          civId: 5,
          civName: 'Britons',
          result: 'win',
          ratingChange: { value: 10 },
        },
      ],
    },
    {
      id: 'team-2',
      name: 'Team 2',
      participants: [
        {
          id: 'p2',
          alias: 'Fr020B',
          civId: 999,
          civName: null,
          result: 'loss',
          ratingChange: { value: -10 },
        },
      ],
    },
  ],
}

export const Archived: Story = {
  name: 'Archived — DownloadAction present',
  args: { match: baseMatch },
}

export const StillCatchable: Story = {
  name: 'Still catchable — DownloadAction absent, not disabled',
  args: {
    match: {
      ...baseMatch,
      gameId: '1003',
      captureStatus: 'pending',
      captureDeadlineAt: new Date(Date.now() + 6 * 24 * 60 * 60_000).toISOString(),
    },
  },
}

export const Lost: Story = {
  name: 'Lost (expired) — DownloadAction absent',
  args: { match: { ...baseMatch, gameId: '1004', captureStatus: 'expired' } },
}

// Cross-checked against capture-state-badge.md's own equivalent criterion: never a download
// affordance for a quarantined capture.
export const NeedsReview: Story = {
  name: 'Needs review — DownloadAction absent (never offered for a quarantined capture)',
  args: { match: { ...baseMatch, gameId: '1005', captureStatus: 'quarantined' } },
}

// Two participants per team: the one shape that can show all three of §8's tiers — one card each
// at 375, two side by side at 768, a ruled table from `xl` (1280) — depending on which width this
// is captured at. `useBreakpoint` reads the real browser window, which this file cannot force (no
// viewport addon is installed here), so this story does not claim to render a single named tier —
// it is the data that makes each tier visible to whoever resizes the window or the review browser
// to it.
export const TeamMatch: Story = {
  name: 'Team match — every participant grouped under its team heading',
  args: { match: teamMatch },
}

export const EightPlayerFreeForAll: Story = {
  name: 'Eight-player free-for-all — eight TeamGroups of one, same anatomy as a 1v1 (§11.4)',
  args: { match: eightPlayerFfaMatch },
}

export const UnnameableIdentifier: Story = {
  name: 'Unresolved civilisation and map — raw identifier, never a guess (FR-020, §11.2)',
  args: { match: unresolvedIdentifierMatch },
}

export const DownloadPreparing: Story = {
  args: { match: baseMatch, downloadState: 'loading' },
}

export const DownloadFailed: Story = {
  name: 'Download failed — button pressable again, StatusRegion shows the reason',
  args: { match: baseMatch, downloadState: 'error' },
}

export const Loading: Story = {
  args: { status: 'loading' },
}

export const LoadFailed: Story = {
  name: 'Load failed — network failure, distinct from "not found"',
  args: { status: 'error' },
}

export const NotFound: Story = {
  name: "Not found — unknown or not the caller's own, indistinguishable (FR-045)",
  args: { status: 'not-found' },
}
