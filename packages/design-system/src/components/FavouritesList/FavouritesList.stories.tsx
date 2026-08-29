import type { Meta, StoryObj } from '@storybook/react-vite'
import type { FavouriteEntryData } from './index'
import { FavouritesList } from './index'

const meta: Meta<typeof FavouritesList> = {
  title: 'Composite/FavouritesList',
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

export const Loading: Story = {
  args: { loading: true, loadingRowCount: 3 },
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
