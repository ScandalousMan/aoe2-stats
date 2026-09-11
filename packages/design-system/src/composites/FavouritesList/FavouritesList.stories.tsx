import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import type { FavouriteEntryData } from './index'
import { FavouritesList } from './index'

const meta: Meta<typeof FavouritesList> = {
  id: 'composite-favouriteslist',
  title: 'Composites/Search & favourites/FavouritesList',
  component: FavouritesList,
  parameters: {
    docs: {
      description: {
        component: `Lets a signed-in user find the players they care about again from one place, without searching.`,
      },
    },
  },
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
// actually renders — six favourites, not `Default`'s three, so this exercises what a short list
// cannot (T581, closing the fifth-pass gap-register row: `Default` and this story used to carry
// byte-identical args, producing baselines that verified nothing of its own):
// - row rhythm and the `space-3`/`gap-3` list padding (favourites-list.md §7) at six rows rather
//   than three, both at the 375 stacked-card width and the wide one-line width `RealisticList`
//   itself renders at;
// - wrapping, not truncation, on a long alias + clan pair at 375 — favourites-list.md §8: "No
//   field truncates or ellipsises … a half-visible alias defeats the point of a bookmark list."
//   `longAlias` below is the case that rule exists for;
// - a rating `delta` in both directions (`StatValue`'s sign glyph, §6 "success/danger … a rating
//   delta's sign"), which neither `Default` nor any other roster in this file carries;
// - one entry mid-removal (`removing: true`) beside entries that are not — `FavouriteToggle`'s
//   own loading spinner (§5 "disabled … RemoveControl is disabled only transiently while its own
//   DELETE is in flight") shown in the realistic context of a longer list, not in isolation.
const longAlias: FavouriteEntryData = {
  profileId: '4',
  href: '/players/4',
  alias: 'TheMongolianEmpireBuilder',
  clan: 'LEGACY',
  country: 'Mongolia',
  standing: { label: 'Rating', value: '1988', unit: '#341', delta: { value: 24 } },
}

const risingRated: FavouriteEntryData = {
  profileId: '5',
  href: '/players/5',
  alias: 'rival_ace',
  country: 'South Korea',
  standing: { label: 'Rating', value: '1842', unit: '#214', delta: { value: 12 } },
}

const fallingRatedRemoving: FavouriteEntryData = {
  profileId: '6',
  href: '/players/6',
  alias: 'Nili_Warrior',
  clan: 'HAI',
  country: 'Netherlands',
  standing: { label: 'Rating', value: '1605', unit: '#1203', delta: { value: -8 } },
  removing: true,
}

export const RealisticList: Story = {
  args: {
    entries: [rated, longAlias, neverRanked, risingRated, staleStanding, fallingRatedRemoving],
  },
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
// share a hover." Forced from Playwright in `tests/visual/stories.spec.ts` (see that file's own
// `VisualForceState` comment) — a `play()` could only dispatch a synthetic event, which the CSS
// pseudo-class ignores.
export const Hover: Story = {
  args: { entries: [rated] },
  parameters: { visualForceState: { state: 'hover', selector: 'a[href="/players/1"]' } },
}

export const FocusVisible: Story = {
  args: { entries: [rated] },
  parameters: { visualForceState: { state: 'focus-visible', selector: 'a[href="/players/1"]' } },
}

export const Active: Story = {
  args: { entries: [rated] },
  parameters: { visualForceState: { state: 'active', selector: 'a[href="/players/1"]' } },
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
