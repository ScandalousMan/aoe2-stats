import type { Meta, StoryObj } from '@storybook/react-vite'
import { Link } from './index'

const meta: Meta<typeof Link> = {
  title: 'Primitives/Link',
  component: Link,
  args: {
    href: '/players/1807091',
    children: 'View profile',
  },
}

export default meta
type Story = StoryObj<typeof Link>

export const Inline: Story = {
  render: (args) => (
    <p className="type-body max-w-measure text-md text-text-primary">
      Every match this profile has played is listed below. To link a different account,{' '}
      <Link {...args}>view its profile</Link> and choose "Link this account" instead.
    </p>
  ),
}

export const Standalone: Story = {
  args: { variant: 'standalone' },
}

export const External: Story = {
  args: {
    href: 'https://store.steampowered.com',
    children: 'Steam',
    external: true,
  },
}

export const StandaloneExternal: Story = {
  args: {
    href: 'https://store.steampowered.com',
    children: 'Open in Steam',
    variant: 'standalone',
    external: true,
  },
}

// §9's hover acceptance criterion: the hover capture differs from the rest capture in *two* ways
// — the ink and the underline thickness (FR-037), captured by hovering the link below with the
// pointer (`tests/visual/stories.spec.ts` drives the real `:hover` state; this story exists so
// there is something to drive).
export const RestAndHover: Story = {
  render: (args) => (
    <div className="flex flex-col gap-1">
      <p className="type-supporting text-sm text-text-secondary">
        Hover the link below: the ink and the underline thickness both change.
      </p>
      <Link {...args} />
    </div>
  ),
}

// §9's token-swatch acceptance criterion: `link`, `link-hover` and `link-visited` painted
// directly, since `:visited` cannot be observed in a real render (browsers restrict it).
export const TokenSwatch: Story = {
  render: () => (
    <div className="flex items-center gap-6">
      <span className="type-body text-md text-link underline decoration-1">link</span>
      <span className="type-body text-md text-link-hover underline decoration-2">link-hover</span>
      <span className="type-body text-md text-link-visited underline decoration-1">
        link-visited
      </span>
    </div>
  ),
}

// A `standalone` link's tappable box must measure at least 44px in both axes at 375 (§9).
export const TouchFootprint: Story = {
  args: { variant: 'standalone', children: 'Export match history' },
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
  },
}

// §9 "empty": no text renders nothing — an icon-only link is forbidden in this tier.
export const Empty: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The link below has no text and renders nothing.
      </p>
      <Link href="/players/1807091">{''}</Link>
    </div>
  ),
}
