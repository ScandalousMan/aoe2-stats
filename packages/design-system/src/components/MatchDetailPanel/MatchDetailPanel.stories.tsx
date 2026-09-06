import type { Meta, StoryObj } from '@storybook/react-vite'
import { MatchDetailPanel } from './index'
import type { MatchDetailData } from './index'

const meta: Meta<typeof MatchDetailPanel> = {
  title: 'Composite/MatchDetailPanel',
  component: MatchDetailPanel,
}

export default meta
type Story = StoryObj<typeof MatchDetailPanel>

// T404's own naming rule: `<name.lower().replace(' ', '_')>.webp` — mirrored here so a story's
// `civIconUrl` names the same file the resolver would (`packages/game-assets/civilisations/`),
// even though a story never calls that resolver itself (`civIconUrl`/`mapThumbnailUrl` are always
// supplied directly, §12.1 rule 3's own "the design system never imports the pack").
function civIconUrl(name: string): string {
  return `/game-assets/civilisations/${name.toLowerCase().replace(/ /g, '_')}.webp`
}

// `StillCatchable`, below, computes a deadline relative to render time so its countdown text
// stays the same no matter which day this story is captured. `Date.now` is frozen for the whole
// iframe — the same technique `CaptureStateBadge.stories.tsx` uses and explains:
// `MatchDetailPanel` renders `CaptureStateBadge` internally, whose own clock (`useTickingNow`)
// reads `Date.now()` independently of the read below, and an unfrozen clock lets those two reads
// land on either side of an exact-unit boundary, flipping the rendered text between runs (T505's
// identity proof).
const FROZEN_NOW_MS = Date.parse('2026-01-01T00:00:00.000Z')
Date.now = () => FROZEN_NOW_MS

const ARABIA_URL = '/game-assets/maps/arabia.webp'

const baseMatch: MatchDetailData = {
  gameId: '1001',
  map: 'Arabia',
  mapThumbnailUrl: ARABIA_URL,
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
          civIconUrl: civIconUrl('Franks'),
          colorId: 4,
          result: 'win',
          rating: 922,
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
          civIconUrl: civIconUrl('Mongols'),
          colorId: 2,
          result: 'loss',
          rating: 894,
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
          civIconUrl: civIconUrl('Franks'),
          colorId: 4,
          result: 'win',
          rating: 913,
          ratingChange: { value: 9 },
        },
        {
          id: 'p2',
          alias: 'aoe2friend',
          civId: 5,
          civName: 'Britons',
          civIconUrl: civIconUrl('Britons'),
          colorId: 3,
          result: 'win',
          rating: 918,
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
          civIconUrl: civIconUrl('Mongols'),
          colorId: 2,
          result: 'loss',
          rating: 887,
          ratingChange: { value: -9 },
        },
        {
          id: 'p4',
          alias: 'aoe2foe',
          civId: 15,
          civName: 'Huns',
          civIconUrl: civIconUrl('Huns'),
          colorId: 6,
          result: 'loss',
          rating: 875,
          ratingChange: { value: -9 },
        },
      ],
    },
  ],
}

// §11.4: "many participants, still one anatomy" — an eight-player free-for-all is eight
// `TeamGroup`s of one, generalising the same `ParticipantsTable` a 1v1 already uses, with no new
// layout branch. Mirrors T430's `EightPlayerMatch` story (match-history.md §12.8) — every mark
// this panel composes (civilisation, colour, rating) is exercised across all eight.
const eightPlayerFfaMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1006',
  leaderboardName: 'Free-for-All',
  teams: [
    {
      civId: 10,
      civName: 'Franks',
      alias: 'aoe2guy',
      colorId: 4,
      result: 'win' as const,
      value: 41,
    },
    {
      civId: 20,
      civName: 'Mongols',
      alias: 'aoe2villain',
      colorId: 2,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 5,
      civName: 'Britons',
      alias: 'aoe2friend',
      colorId: 3,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 15,
      civName: 'Huns',
      alias: 'aoe2foe',
      colorId: 6,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 3,
      civName: 'Aztecs',
      alias: 'aoe2rando1',
      colorId: 5,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 8,
      civName: 'Byzantines',
      alias: 'aoe2rando2',
      colorId: 7,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 1,
      civName: 'Aztecs',
      alias: 'aoe2rando3',
      colorId: 8,
      result: 'loss' as const,
      value: -6,
    },
    {
      civId: 30,
      civName: 'Mayans',
      alias: 'aoe2rando4',
      colorId: 1,
      result: 'loss' as const,
      value: -5,
    },
  ].map((p, index) => ({
    id: `team-${index + 1}`,
    name: `Team ${index + 1}`,
    participants: [
      {
        id: `p${index + 1}`,
        alias: p.alias,
        civId: p.civId,
        civName: p.civName,
        civIconUrl: civIconUrl(p.civName),
        colorId: p.colorId,
        result: p.result,
        rating: 950 + p.value,
        ratingChange: { value: p.value },
      },
    ],
  })),
}

// §11.2: FR-020, no guess. `Fr020B`'s civilisation is a game-version id this service's reference
// data has never learned, and the header's map carries no name either — placed alongside a fully
// resolved participant so the visual distinction (`type-identifier` vs `text-primary`/`sans`,
// T531, research D7) reads in one frame (§11.6).
const unresolvedIdentifierMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1007',
  map: null,
  mapThumbnailUrl: undefined,
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
          civIconUrl: civIconUrl('Britons'),
          colorId: 4,
          result: 'win',
          rating: 930,
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
          colorId: 2,
          result: 'loss',
          rating: 870,
          ratingChange: { value: -10 },
        },
      ],
    },
  ],
}

// match-history.md §2a — a resolved win and a resolved loss beside an unknown result, so the
// distinct wording ("Win" / "Loss" / "Unknown") and the distinct colour step (`text-secondary`,
// never `success`/`danger`) both read in one frame.
const mixedResultMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1008',
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
          civIconUrl: civIconUrl('Franks'),
          colorId: 4,
          result: 'win',
          rating: 934,
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
          civIconUrl: civIconUrl('Mongols'),
          colorId: 2,
          result: 'unknown',
        },
      ],
    },
  ],
}

// §2a's own reproduction: `match_players.result` is `null` for every row this system has written
// so far — this is the eight-player match a real production page showed as eight losses before
// this fix. No participant here carries a rating change either, matching that same gap
// (`rating_diff` is derived from the result this ingestion stage has not recorded) — colour,
// unlike rating, is a read-time enrichment independent of that gap (data-model.md §6), so it is
// still shown. Mirrors T430's `NullResult` story (match-history.md §12.6/§12.8).
const allUnknownResultMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1009',
  leaderboardName: 'Free-for-All',
  teams: [
    { civId: 10, civName: 'Franks', alias: 'aoe2guy', colorId: 4 },
    { civId: 20, civName: 'Mongols', alias: 'aoe2villain', colorId: 2 },
    { civId: 5, civName: 'Britons', alias: 'aoe2friend', colorId: 3 },
    { civId: 15, civName: 'Huns', alias: 'aoe2foe', colorId: 6 },
    { civId: 3, civName: 'Aztecs', alias: 'aoe2rando1', colorId: 5 },
    { civId: 8, civName: 'Byzantines', alias: 'aoe2rando2', colorId: 7 },
    { civId: 1, civName: 'Aztecs', alias: 'aoe2rando3', colorId: 8 },
    { civId: 30, civName: 'Mayans', alias: 'aoe2rando4', colorId: 1 },
  ].map((p, index) => ({
    id: `team-${index + 1}`,
    name: `Team ${index + 1}`,
    participants: [
      {
        id: `p${index + 1}`,
        alias: p.alias,
        civId: p.civId,
        civName: p.civName,
        civIconUrl: civIconUrl(p.civName),
        colorId: p.colorId,
        result: 'unknown' as const,
      },
    ],
  })),
}

// §12.1 rule 3: the absent-asset state is the prop being `undefined` — no box, no silhouette, no
// "?" tile. Every mark this panel can carry is uncovered at once: the civilisation icon, the map
// thumbnail, and every participant's colour. Mirrors T430's `NoAssetsCovered` story
// (match-history.md §12.1 rule 3, §12.8) — the same civilisation and map names, so the two
// components' degrade paths can be compared side by side.
const noAssetsCoveredMatch: MatchDetailData = {
  ...baseMatch,
  gameId: '1010',
  map: 'A Custom Tournament Map',
  mapThumbnailUrl: undefined,
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'aoe2guy',
          civId: 40,
          civName: 'Gurjaras',
          civIconUrl: undefined,
          colorId: null,
          result: 'win',
          rating: 934,
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
          civId: 41,
          civName: 'Bengalis',
          civIconUrl: undefined,
          colorId: null,
          result: 'loss',
          rating: 901,
          ratingChange: { value: -12 },
        },
      ],
    },
  ],
}

export const Archived: Story = {
  name: 'Archived — 1v1, DownloadAction present (§12.5 mark composition)',
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

// --- §12.8: the four scenarios T431 mirrors from T430 -------------------------------------------

export const EightPlayerMatch: Story = {
  name: 'Eight-player match — eight TeamGroups of one, same anatomy as a 1v1 (§11.4, §12.8)',
  args: { match: eightPlayerFfaMatch },
}

export const UnnameableIdentifier: Story = {
  name: 'Unresolved civilisation and map — raw identifier, never a guess (FR-020, §11.2)',
  args: { match: unresolvedIdentifierMatch },
}

export const MixedResult: Story = {
  name: 'Unknown result beside a win and a loss — "Unknown", never "Loss" (§2a)',
  args: { match: mixedResultMatch },
}

export const NullResult: Story = {
  name: 'A null result — every participant unknown, the production reproduction (§2a, §12.8)',
  args: { match: allUnknownResultMatch },
}

export const NoAssetsCovered: Story = {
  name: 'No assets covered — unknown civ icon, unknown map thumbnail, no colour (§12.1 rule 3, §12.8)',
  args: { match: noAssetsCoveredMatch },
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
