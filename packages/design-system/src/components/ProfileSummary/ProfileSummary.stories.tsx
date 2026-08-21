import type { Meta, StoryObj } from '@storybook/react-vite'
import { ProfileSummary } from './index'
import type { RatingEntryData } from './index'

const meta: Meta<typeof ProfileSummary> = {
  title: 'Screens/ProfileSummary',
  component: ProfileSummary,
}

export default meta
type Story = StoryObj<typeof ProfileSummary>

const entries: RatingEntryData[] = [
  {
    leaderboardId: '1v1-rm',
    leaderboardName: '1v1 Random Map',
    rating: '1842',
    ratingDelta: { value: 12 },
    rank: '#214',
    wins: 142,
    losses: 118,
    winRate: '55%',
    streak: 'W3',
    highestRating: '1901',
  },
  {
    leaderboardId: 'tg-rm',
    leaderboardName: 'Team Random Map',
    rating: '1690',
    ratingDelta: { value: -8 },
    wins: 60,
    losses: 55,
    winRate: '52%',
  },
]

const viewedProfile = {
  id: 'p1',
  alias: 'aoe2guy',
  country: 'France',
  profileId: '12345678',
  isPrimary: true,
}

const linkedProfiles = [
  { id: 'p1', alias: 'aoe2guy', isPrimary: true },
  { id: 'p2', alias: 'aoe2alt', isPrimary: false },
]

export const Board: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

export const SingleLinkedProfile: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles: [linkedProfiles[0]],
    entries,
  },
}

export const ViewingNonPrimary: Story = {
  args: {
    authenticated: true,
    viewedProfile: { ...viewedProfile, id: 'p2', alias: 'aoe2alt', isPrimary: false },
    linkedProfiles,
    entries,
  },
}

export const Unauthenticated: Story = {
  args: {
    authenticated: false,
    viewedProfile,
    entries,
  },
}

export const Loading: Story = {
  args: {
    authenticated: true,
    entries: [],
    status: 'loading',
  },
}

export const StaleAfterFailedRefresh: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    status: 'stale',
    freshnessLine: 'Measured 2 hours ago',
  },
}

export const NeverLoadedError: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries: [],
    status: 'error',
  },
}

export const EmptyNoRatedLeaderboard: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries: [],
  },
}

export const ProvisionalRank: Story = {
  args: {
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries: [{ ...entries[0], rank: undefined }],
  },
}

export const CompactVariant: Story = {
  args: {
    variant: 'compact',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries: [entries[0]],
  },
}
