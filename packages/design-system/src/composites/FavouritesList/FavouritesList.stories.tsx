import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor } from 'storybook/test'
import type { FavouriteEntryData } from './index'
import { FavouritesList } from './index'

const meta: Meta<typeof FavouritesList> = {
  id: 'composite-favouriteslist',
  title: 'Composites/Search & favourites/FavouritesList',
  component: FavouritesList,
}

export default meta
type Story = StoryObj<typeof FavouritesList>

const rated: FavouriteEntryData = {
  profileId: '1',
  href: '/players/1',
  alias: 'GL.TheViper',
  clan: 'GL',
  country: 'France',
  standing: { label: 'Rating', value: '2450', unit: '#3' },
}

const neverRanked: FavouriteEntryData = {
  profileId: '2',
  href: '/players/2',
  alias: 'newplayer99',
  country: 'Germany',
  standing: { status: 'empty', label: 'Rating', secondaryLine: 'Not ranked yet' },
}

const staleStanding: FavouriteEntryData = {
  profileId: '3',
  href: '/players/3',
  alias: 'DauT',
  country: 'Israel',
  standing: {
    label: 'Rating',
    value: '2380',
    unit: '#9',
    secondaryLine: 'Measured 12 Aug 2026 · could not refresh',
  },
}

export const Default: Story = {
  args: { entries: [rated, neverRanked, staleStanding] },
}

// §4: a favourite who never played a ranked ladder shows StatValue's empty state, never `0`.
export const NeverRankedEntry: Story = {
  name: 'A favourite who never played ranked (§4)',
  args: { entries: [neverRanked] },
}

// §4: standing that could not be refreshed shows the last-known figure at full contrast, labelled
// stale — the row still links to the profile rather than being dropped.
export const UnrefreshableStanding: Story = {
  name: 'A favourite whose standing could not refresh (§4)',
  args: { entries: [staleStanding] },
}

// `loading: true` renders `Skeleton` rows, which stay invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  args: { loading: true, loadingRowCount: 3 },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

export const LoadFailed: Story = {
  name: 'Error — GET /api/favourites failed (§5)',
  args: { error: true },
}

export const Empty: Story = {
  name: 'Empty — signed in, no favourites yet (§5)',
  args: { entries: [] },
}

// §5a, US5 scenario 5, FR-015 — no favourited player anywhere in the frame; a real "Sign in"
// action that carries `/favourites` as the return location.
export const SignedOut: Story = {
  name: 'Signed out (§5a, FR-015)',
  args: {
    authenticated: false,
    signInHref: '/sign-in?returnTo=%2Ffavourites',
    // Even if a caller mistakenly supplied entries alongside `authenticated: false`, none may
    // render — the signed-out branch takes priority over every other prop.
    entries: [rated],
  },
}

// A realistic combined story: a mixed roster, the shape `apps/web`'s /favourites route (T349)
// actually renders.
export const RealisticList: Story = {
  args: { entries: [rated, neverRanked, staleStanding] },
}

// FR-044: `FavouriteRow`'s own doc comment (§8) names `md` as the breakpoint — a stacked
// full-width card below it, one line with a right-aligned remove control from it. Pinned toward
// the narrow shape with the declared `reviewWidthNarrow` viewport via `globals.viewport` (see
// `MatchRow.stories.tsx`'s identical rationale for why a declared option rather than a Storybook
// device preset) — `RealisticList` above already reads at the wide, one-line shape.
export const StackedBelowMd: Story = {
  name: 'Stacked card below md, one line from it (§8)',
  globals: { viewport: { value: 'reviewWidthNarrow' } },
  args: { entries: [rated, neverRanked, staleStanding] },
}

// favourites-list.md §5 "hover / focus-visible / active — `ProfileLink`: whole-block hover fill
// `surface-sunken`... `RemoveControl`: `FavouriteToggle`'s own hover/focus/active. The two never
// share a hover."
export const Hover: Story = {
  args: { entries: [rated] },
  play: async ({ canvasElement }) => {
    const link = canvasElement.querySelector('a[href="/players/1"]')
    if (link) await userEvent.hover(link)
  },
}

export const FocusVisible: Story = {
  args: { entries: [rated] },
  play: async () => {
    await userEvent.tab()
  },
}

export const Active: Story = {
  args: { entries: [rated] },
  play: async ({ canvasElement }) => {
    const link = canvasElement.querySelector('a[href="/players/1"]')
    if (link) await userEvent.pointer({ keys: '[MouseLeft>]', target: link })
  },
}

// §5 "disabled — the list has no disabled form. `RemoveControl` is disabled only transiently
// while its own `DELETE` is in flight."
export const DisabledNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The list itself has no disabled form. Its remove control disables only transiently while its
        own removal request is in flight — see `FavouriteToggle`'s own loading story.
      </p>
      <FavouritesList {...args} />
    </div>
  ),
  args: { entries: [rated] },
}
