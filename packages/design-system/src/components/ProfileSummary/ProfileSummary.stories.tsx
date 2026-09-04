import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
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

// T457 remediation (004 spec §13.3/§13.8) — the contrast case a short alias cannot exercise: a
// 19-character alias, long enough that the switcher trigger's own preferred width can exceed what
// is left of the name line once the flag's 44px box and its `space-3` are accounted for at 375.
// The fix (NameLine `nowrap` + a truncating alias) must hold here exactly as it does for
// `aoe2guy` — the flag stays "one 44px mark on the name line" (§13.8), never wrapped beneath the
// switcher where its `block-start` tooltip would collide with it.
const longAliasProfile = {
  ...viewedProfile,
  alias: 'TheUndefeatedAoE2GM',
}

const longAliasLinkedProfiles = [
  { id: 'p1', alias: 'TheUndefeatedAoE2GM', isPrimary: true },
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

// 004 spec §13.9 — the full-profile story: avatar leading, alias as the heading, the country flag
// alone (no country word anywhere in the frame — the name lives in the flag's tooltip, T457), and
// the numeric id demoted beneath in `text-secondary`.
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

// T457 remediation (004 spec §13.3/§13.8) — the resting (tooltip-closed) `Board` frame at 375,
// where the defect actually lived: the flag must stay on the name line beside the switcher
// trigger, not wrap beneath it, and the identity bar must not force the page wider than the
// viewport. `visual-mobile` is the tag that captures this width at all — see the comment on
// `BoardFlagHoverRevealed` below.
export const BoardMobile: Story = {
  name: 'Board at 375 — the flag stays on the name line, resting (004 §13.8, T457)',
  tags: ['visual-mobile'],
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// T457 remediation, contrast case — the same 375 frame with a 19-character alias instead of
// `aoe2guy`. The switcher trigger's alias truncates before the flag ever gives up its line: no
// horizontal overflow, and the flag still lands beside the trigger, not beneath it.
export const BoardLongAliasMobile: Story = {
  name: 'Board at 375, long alias — the alias truncates, the flag does not wrap (004 §13.8, T457)',
  tags: ['visual-mobile'],
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: longAliasProfile,
    linkedProfiles: longAliasLinkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// 004 spec §13.9 — the flag-hover story: the country name in a tooltip above the flag, not
// covering the rating board beneath the identity bar.
async function hoverFlagOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  const flag = canvas.getByRole('button', { name: /^Country: / })
  await userEvent.hover(flag)
  await canvas.findByRole('tooltip')
}

// 004 spec §13.9 — the flag-focus story: Tab order is switcher trigger → flag → actions; the
// tooltip opens immediately and the flag's own focus ring stays in the same frame.
async function focusFlagOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.tab() // switcher trigger (or the fallback heading has no stop to land on)
  await userEvent.tab() // the flag
  await canvas.findByRole('tooltip')
}

// 004 spec §13.9 — the flag-pinned story: the touch route, no pointer over the flag, no focus ring.
async function pinFlagOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  const flag = canvas.getByRole('button', { name: /^Country: / })
  await userEvent.click(flag)
  await canvas.findByRole('tooltip')
  await userEvent.unhover(flag)
  flag.blur()
  await waitFor(() => expect(flag).not.toHaveFocus())
}

// `visual-mobile`: this is the one viewport where the flag can be pushed onto the switcher
// trigger's line (T457) — the defect was invisible at the suite's default desktop width, exactly
// the PrivacyNotice T096 lesson `scripts/visual/run.mjs` documents for this tag.
export const BoardFlagHoverRevealed: Story = {
  name: 'Flag hover — country name in a tooltip above the flag (004 §13.9)',
  tags: ['visual-full-page', 'visual-mobile'],
  play: hoverFlagOpen,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

export const BoardFlagKeyboardFocusRevealed: Story = {
  name: 'Flag keyboard focus — tooltip open and focus ring together (004 §13.9)',
  tags: ['visual-full-page', 'visual-mobile'],
  play: focusFlagOpen,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

export const BoardFlagPinned: Story = {
  name: 'Flag pinned — the touch route, no pointer, no focus ring (004 §13.9)',
  tags: ['visual-full-page', 'visual-mobile'],
  play: pinFlagOpen,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// T457 remediation, contrast case (004 spec §13.3/§13.8) — the same hover-revealed tooltip as
// `BoardFlagHoverRevealed`, with a 19-character alias instead of `aoe2guy`. Proves the fix's shape,
// not just its instance: the switcher trigger's alias truncates rather than pushing the flag onto
// its own line, so the flag stays on the name line and its upward tooltip still lands clear of the
// switcher trigger and the alias, exactly as it does for a short alias.
export const BoardLongAliasFlagHoverRevealed: Story = {
  name: 'Flag hover, long alias — the fix holds when the alias is 19 characters, not 7 (004 §13.8, T457)',
  tags: ['visual-full-page', 'visual-mobile'],
  play: hoverFlagOpen,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: longAliasProfile,
    linkedProfiles: longAliasLinkedProfiles,
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

// spec §3: `compact` shows the primary (first) leaderboard's rating and rank only, on one row —
// the switcher stays. Both leaderboards are passed here (not pre-sliced to `entries[0]`) so the
// visual baseline actually exercises the "second leaderboard is not shown" rule instead of hiding
// it by construction.
export const CompactVariant: Story = {
  args: {
    variant: 'compact',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
  },
}
