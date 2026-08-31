import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { ProfileSummary } from './index'
import type { RatingEntryData } from './index'

const meta: Meta<typeof ProfileSummary> = {
  title: 'Screens/ProfileSummary',
  component: ProfileSummary,
}

export default meta
type Story = StoryObj<typeof ProfileSummary>

// A fixture hash — the visual test runner stubs the CDN request this URL resolves to
// (`player-avatar.md` §9's "the visual baseline must not depend on Steam"), never a real Steam
// hash. Shared with `PlayerAvatar.stories.tsx`'s own `FIXTURE_HASH` so one stub in
// `tests/visual/stories.spec.ts` covers both.
const FIXTURE_AVATAR_HASH = '0123456789abcdef0123456789abcdef01234567'

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
  countryName: 'France',
  countryFlagUrl: '/game-assets/flags/fr.svg',
  avatarHash: FIXTURE_AVATAR_HASH,
  profileId: '12345678',
  isPrimary: true,
}

const linkedProfiles = [
  { id: 'p1', alias: 'aoe2guy', isPrimary: true },
  { id: 'p2', alias: 'aoe2alt', isPrimary: false },
]

// 003 spec §11 — a third party's profile, reached from search rather than `/api/me`. Same
// `RatingEntryData` shape and the same `entries` fixture as `Board`, so the two stories are
// comparable digit-for-digit in `RatingBoard` (spec §11.4's last bullet).
const thirdPartyProfile = {
  id: 'p9',
  alias: 'rival_ace',
  countryName: 'Germany',
  countryFlagUrl: '/game-assets/flags/de.svg',
  avatarHash: FIXTURE_AVATAR_HASH,
  profileId: '87654321',
  isPrimary: false,
}

// A stub only — the real toggle, its state and its mutation are 003's US5 (T348). This story
// exists to prove `ProfileSummary` renders whatever is placed in the seam, not to implement it.
const favouriteToggleStub = (
  <Button variant="ghost" aria-pressed={false}>
    Add to favourites
  </Button>
)

// 004 spec §12.9 — the full-profile story: avatar leading, alias as the heading, a flag with the
// country name beside it, and the numeric id demoted beneath in `text-secondary`.
export const Board: Story = {
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// 004 spec §12.3 (Rule 1) — no alias at all: the heading reads "Player <id>" in `font-mono` at the
// alias's own size, `ProfileId` is omitted (the id already is the heading) and no
// `AliasFreshnessNote` appears. The id appears exactly once in the frame.
export const NoAlias: Story = {
  name: 'No alias — heading falls back to "Player <id>" (004 FR-007)',
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: { ...viewedProfile, alias: '', profileId: '1807091' },
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// 004 spec §12.4 (Rule 2) — no country: the flag and its label are both absent, and the line
// closes up. No reserved gap, no em dash, no "Unknown country".
export const NoCountry: Story = {
  name: 'No country — the flag and its label are both absent, cleanly (004 FR-008)',
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: { ...viewedProfile, countryName: undefined, countryFlagUrl: undefined },
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// 004 spec §12.7 — the shape of a profile this service discovered from a match and never
// enriched: profile `1807091` (spec.md's own example), never searched, never seen by the
// companion provider. All three fallback-ladder rules fire at once, and "No ratings yet" is
// still the correct, calm rendering underneath — not a warning, not an error.
export const DiscoveredNeverEnrichedNeverRanked: Story = {
  name: 'No alias, no country, no avatar, no ratings — a real resting state, not a failure (004 spec §12.7)',
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: {
      id: 'p1807091',
      alias: '',
      countryName: undefined,
      countryFlagUrl: undefined,
      avatarHash: undefined,
      profileId: '1807091',
      isPrimary: true,
    },
    linkedProfiles: [{ id: 'p1807091', alias: '1807091', isPrimary: true }],
    entries: [],
  },
}

export const ViewingThirdParty: Story = {
  args: {
    subject: 'other',
    authenticated: true,
    viewedProfile: thirdPartyProfile,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
    aliasObservedAtLabel: '12 Aug 2026',
    favouriteToggle: favouriteToggleStub,
  },
}

export const ThirdPartyNeverRanked: Story = {
  args: {
    subject: 'other',
    authenticated: true,
    viewedProfile: thirdPartyProfile,
    entries: [],
    aliasObservedAtLabel: '12 Aug 2026',
    favouriteToggle: favouriteToggleStub,
  },
}

export const ThirdPartyNotFound: Story = {
  args: {
    subject: 'other',
    authenticated: true,
    entries: [],
    status: 'not-found',
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
