import type { Meta, StoryObj } from '@storybook/react-vite'
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
  tags: ['visual-mobile'],
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
  tags: ['visual-mobile'],
  args: { items: longLabelItems, currentPath: '/dashboard' },
}
