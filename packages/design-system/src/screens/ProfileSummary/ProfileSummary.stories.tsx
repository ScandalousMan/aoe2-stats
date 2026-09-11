import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { Button } from '../../primitives/Button'
import { ProfileSummary } from './index'
import type { RatingEntryData } from './index'

const meta: Meta<typeof ProfileSummary> = {
  id: 'screens-profilesummary',
  title: 'Screens/Profile & capture/ProfileSummary',
  component: ProfileSummary,
  parameters: {
    docs: {
      description: {
        component: `Shows who the user is on the leaderboards — rating, rank and win/loss on every board they play — and makes their other linked profiles reachable in one gesture.`,
      },
    },
  },
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

// FR-044: `index.tsx`'s own `isTable = useBreakpoint('lg')` — ratings render as cards below `lg`
// (1024) and as a `<table>` from it. Pinned toward the narrow shape with the declared
// `reviewWidthNarrow` viewport via `globals.viewport` (see `MatchRow.stories.tsx`'s identical
// rationale for why a declared option rather than a Storybook device preset) — `Board` above
// already reads at the wide, table shape.
export const BoardRatingsCardsBelowLg: Story = {
  name: 'Ratings as cards below lg, a table from it',
  globals: { viewport: { value: 'reviewWidthNarrow' } },
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
// viewport. Every story is now captured at 375px as a matter of course (T504), so no tag is
// needed to reach that width.
export const BoardMobile: Story = {
  name: 'Board at 375 — the flag stays on the name line, resting (004 §13.8, T457)',
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

// 375 is the one width where the flag can be pushed onto the switcher trigger's line (T457) —
// the defect was invisible at the suite's default desktop width. Every story is now captured at
// 375px as a matter of course (T504), so `visual-full-page` is the only tag this needs.
// Remediation (fifth-pass review, B1): `play: hoverFlagOpen` opens the tooltip for real (the
// synthetic `userEvent.hover` still reaches `Tooltip`'s own listener), but never sets Chromium's
// actual `:hover` pseudo-class — `visualForceState` drives that separately, after `play()` has
// settled, matched by the flag's own accessible name (`role: 'button'` alone would be ambiguous
// here: the profile switcher trigger is also a button in this frame).
export const BoardFlagHoverRevealed: Story = {
  name: 'Flag hover — country name in a tooltip above the flag (004 §13.9)',
  tags: ['visual-full-page'],
  play: hoverFlagOpen,
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
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
  tags: ['visual-full-page'],
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
  tags: ['visual-full-page'],
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
// Remediation (fifth-pass review, B1 sweep): the same gap as `BoardFlagHoverRevealed` above — a
// `Hover`-named story with a `play()` that never set the real `:hover` pseudo-class. Not in the
// review's own named list, found by sweeping every `Hover`/`Active`/`FocusVisible`-named story in
// scope for a missing `visualForceState` rather than trusting that list.
export const BoardLongAliasFlagHoverRevealed: Story = {
  name: 'Flag hover, long alias — the fix holds when the alias is 19 characters, not 7 (004 §13.8, T457)',
  tags: ['visual-full-page'],
  play: hoverFlagOpen,
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: longAliasProfile,
    linkedProfiles: longAliasLinkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// 004 spec §12.3 (Rule 1) — no alias at all: the heading reads "Player <id>" in `type-identifier`
// (T531, research D7 — amended from the pre-typography-role `font-mono`/`text-primary`) at the
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

// `status: 'loading'` renders `Skeleton`, which stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  args: {
    authenticated: true,
    entries: [],
    status: 'loading',
  },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
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

// profile-summary.md §5 "hover — switcher trigger and menu items per `Menu`. A `RatingEntry` is
// not interactive in this feature... and therefore has no hover affordance." / "focus-visible —
// standard ring on the trigger, on menu items, and on the ghost actions." / "active — per `Button`
// and `Menu`." The switcher's own hover/focus/active are `Menu`'s stories (`ProfileSwitcher`); this
// opens it here by keyboard, the same technique `SiteHeader`'s `ThemeControl` stories use, and
// calls out the one part that has none of its own.
async function openSwitcher({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  // Matched by the trigger's own accessible name suffix (`${headingAlias}, switch profile`,
  // index.tsx) rather than a hardcoded alias, so this helper still finds the trigger in a story
  // whose `viewedProfile` is not `aoe2guy` (the `Selection` story below views `aoe2alt`).
  const trigger = canvas.getByRole('button', { name: /switch profile$/ })
  trigger.focus()
  await userEvent.keyboard('{Enter}')
  await canvas.findByRole('menu')
}

// The **other** `Menu` on this screen (`triggerLabel="Manage"`, index.tsx) — the one
// `unlinkInFlight`/`primaryChangeInFlight` items actually live in (`manageItems`, index.tsx). A
// story depicting one of those two states must open this menu, not the profile switcher opened by
// `openSwitcher` above: the switcher's own items know nothing of `unlinkInFlight`.
async function openManage({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  const trigger = canvas.getByRole('button', { name: 'Manage' })
  trigger.focus()
  await userEvent.keyboard('{Enter}')
  await canvas.findByRole('menu')
}

export const SwitcherFocusVisibleAndOpen: Story = {
  tags: ['visual-full-page'],
  play: openSwitcher,
  // `openSwitcher`'s own `Enter` press already moves DOM focus to the checked item (`Menu`'s own
  // `itemRefs.current[activeIndex]?.focus()`, index.tsx) — `viewedProfile` here is `p1`/`aoe2guy`,
  // the item `linkedProfiles` marks checked — but this story's name promises a real `:focus-visible`
  // ring, which only `tests/visual/stories.spec.ts`'s own forced pseudo-class (never a story's own
  // synthetic `play()`) reliably paints (see that file's `VisualForceState` comment). Named the same
  // way `Button.stories.tsx`'s `Hover`/`Active`/`FocusVisible` and `Menu.stories.tsx`'s own
  // `focus-visible` stories already are.
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' },
  },
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// FR-034/FR-037, T569 residual 1 and 2: a story named for the *selection* vocabulary entry, and
// deliberately the case `SwitcherFocusVisibleAndOpen` above cannot exercise — there, the viewed
// profile (`aoe2guy`) is also the primary one, so the checked item's `<Badge>Current</Badge>` and
// the primary item's `<Badge variant="accent">Primary</Badge>` would land on the same row and the
// defect (no mark at all for a checked-but-not-primary item) stayed invisible. Here `viewedProfile`
// is `aoe2alt`, non-primary, so this frame is the still-image proof that the checked profile now
// carries its own mark independent of `isPrimary` — the same `Menu`/`selection` idiom `SiteHeader`'s
// `ThemeControl` already ships (`shared-primitives.md#Menu`'s "the checked item is marked by text
// or a `Badge`, not by colour alone").
export const Selection: Story = {
  tags: ['visual-full-page'],
  play: openSwitcher,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: { ...viewedProfile, id: 'p2', alias: 'aoe2alt', isPrimary: false },
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

export const RatingEntryHoverNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A `RatingEntry` is not interactive in this feature — rating history is a later route — so it
        has no hover affordance of its own. The switcher trigger and its menu items carry theirs,
        per `Menu`.
      </p>
      <ProfileSummary {...args} />
    </div>
  ),
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
  },
}

// §5 "disabled — the primary profile's own 'Make primary' item is absent, not disabled... While a
// primary change is in flight, every menu item is `aria-disabled` and the target item shows the
// `Menu` loading state."
// Remediation (the same defect `UnlinkInFlight` below was already fixed for): `primaryChangeInFlight`
// drives the "Make primary" item inside the **Manage** menu (`manageItems`, index.tsx), not the
// profile switcher — `openSwitcher` opened the wrong surface. Worse, "Make primary" only exists
// when `viewedProfile.isPrimary` is false (index.tsx's `manageItems`) — this story's own fixture
// used the module-level `viewedProfile`, whose `isPrimary` is `true`, which removes the item this
// story exists to show entirely. `openManage` opens the right menu, and the non-primary fixture
// `Selection` above already uses is what makes the item exist to load.
export const PrimaryChangeInFlight: Story = {
  tags: ['visual-full-page'],
  play: openManage,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile: { ...viewedProfile, id: 'p2', alias: 'aoe2alt', isPrimary: false },
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
    primaryChangeInFlight: true,
  },
}

// §5 "disabled — ... The unlink action is disabled only while an unlink is in flight."
export const UnlinkInFlight: Story = {
  tags: ['visual-full-page'],
  // Remediation: `unlinkInFlight` drives the "Unlink this profile" item inside the **Manage**
  // menu, not the profile switcher — `openSwitcher` opened the wrong surface, so this story
  // captured a switcher frame with nothing loading in it. `openManage` opens the menu the item
  // actually lives in.
  play: openManage,
  args: {
    subject: 'self',
    authenticated: true,
    viewedProfile,
    linkedProfiles,
    entries,
    freshnessLine: 'Measured 3 minutes ago',
    unlinkInFlight: true,
  },
}
