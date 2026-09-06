import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { THEME_STORAGE_KEY } from '../../theme'
import { SiteHeader, type SiteHeaderNavItem } from './index'

const meta: Meta<typeof SiteHeader> = {
  title: 'Chrome/SiteHeader',
  component: SiteHeader,
}

export default meta
type Story = StoryObj<typeof SiteHeader>

// §3a's canonical item set for 004 — fixed here so the signed-in stories match what T442 actually
// mounts, rather than each story inventing its own list.
const items: SiteHeaderNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
  { id: 'matches', label: 'Matches', href: '/matches' },
  { id: 'search', label: 'Search', href: '/search' },
  { id: 'favourites', label: 'Favourites', href: '/favourites' },
  { id: 'my-data', label: 'My data', href: '/privacy' },
]

export const SignedIn: Story = {
  name: 'signed in — Dashboard is current',
  args: { items, currentPath: '/dashboard' },
}

export const CurrentIsNestedRoute: Story = {
  name: 'current path is a nested route — /matches/12345 still marks Matches (§4)',
  args: { items, currentPath: '/matches/12345' },
}

export const NoCurrentItem: Story = {
  name: 'no item matches — every item at rest, none heavier, none marked (§5 empty)',
  args: { items, currentPath: '/players/1807091' },
}

export const SignedOut: Story = {
  name: 'signed out — items={[]}, no <nav>, wordmark and skip link only',
  args: { items: [] },
}

export const SmallViewport: Story = {
  name: '375px — Brand alone on the first row, items wrap beneath it (§8)',
  args: { items, currentPath: '/dashboard' },
}

// The longest plausible item set, at 375: the label lengths §3a's real set never reaches, so the
// wrap-not-truncate rule (§10, §8) has something to actually prove itself against.
const longLabelItems: SiteHeaderNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
  { id: 'matches', label: 'Match history', href: '/matches' },
  { id: 'search', label: 'Find a player', href: '/search' },
  { id: 'favourites', label: 'Favourite players', href: '/favourites' },
  { id: 'my-data', label: 'My data and privacy', href: '/privacy' },
]

export const LongLabels: Story = {
  name: '375px — the longest plausible item set, wrapping onto further rows, nothing truncated',
  args: { items: longLabelItems, currentPath: '/dashboard' },
}

// §ThemeControl (T535, FR-014): the three-state control, one story per state. Each seeds
// `localStorage` in a `loader` — which resolves *before* `SiteHeader` (and the `ThemeProvider` it
// owns internally) ever mounts — rather than clicking the option live: clicking "Light" or "Dark"
// really does call `setOverride`, which paints `document.documentElement`'s own theme attribute,
// and that would fight the very `theme:<light|dark>` global this suite's dual-theme capture
// depends on (`preview.tsx`'s decorator sets that same attribute for the axis being captured).
// Seeding the stored override instead leaves that attribute alone: these three stories differ only
// in which of the three states `useTheme()` reports, never in which theme the page itself paints,
// so their light and dark captures are the same three states artificial-lit two different ways —
// exactly what the rest of this suite's matrix already does for every other story.
async function openThemeControl({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.click(canvas.getByRole('button', { name: /^Theme:/ }))
  await canvas.findByRole('menu')
}

export const ThemeControlFollowingSystem: Story = {
  tags: ['visual-full-page'],
  name: 'theme control — following the system, no stored override (§ThemeControl)',
  loaders: [
    async () => {
      localStorage.removeItem(THEME_STORAGE_KEY)
      return {}
    },
  ],
  play: openThemeControl,
  args: { items, currentPath: '/dashboard' },
}

export const ThemeControlSetToLight: Story = {
  tags: ['visual-full-page'],
  name: 'theme control — the reader has chosen Light (§ThemeControl)',
  loaders: [
    async () => {
      localStorage.setItem(THEME_STORAGE_KEY, 'light')
      return {}
    },
  ],
  play: openThemeControl,
  args: { items, currentPath: '/dashboard' },
}

export const ThemeControlSetToDark: Story = {
  tags: ['visual-full-page'],
  name: 'theme control — the reader has chosen Dark (§ThemeControl)',
  loaders: [
    async () => {
      localStorage.setItem(THEME_STORAGE_KEY, 'dark')
      return {}
    },
  ],
  play: openThemeControl,
  args: { items, currentPath: '/dashboard' },
}
