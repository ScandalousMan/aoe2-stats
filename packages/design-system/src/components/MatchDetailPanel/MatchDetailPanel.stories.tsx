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
          civilisation: 'Franks',
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
          civilisation: 'Mongols',
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
          civilisation: 'Franks',
          result: 'win',
          ratingChange: { value: 9 },
        },
        {
          id: 'p2',
          alias: 'aoe2friend',
          civilisation: 'Britons',
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
          civilisation: 'Mongols',
          result: 'loss',
          ratingChange: { value: -9 },
        },
        {
          id: 'p4',
          alias: 'aoe2foe',
          civilisation: 'Huns',
          result: 'loss',
          ratingChange: { value: -9 },
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

export const TeamMatch: Story = {
  name: 'Team match — every participant grouped under its team heading',
  args: { match: teamMatch },
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
