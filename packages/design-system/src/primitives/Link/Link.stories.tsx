import type { Meta, StoryObj } from '@storybook/react-vite'
import { Link } from './index'

const meta: Meta<typeof Link> = {
  id: 'primitives-link',
  title: 'Primitives/Typography/Link',
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

// A `standalone` link's tappable box must measure at least 44px in both axes at the narrow review
// width (§9). Pinned to `reviewWidthNarrow` (`.storybook/preview.tsx`, see `MatchRow.stories.tsx`'s
// identical rationale for why a declared option rather than a Storybook device preset) — this pin
// serves the browsable Storybook only; the visual suite's own `WIDTHS` axis governs a baseline.
export const TouchFootprint: Story = {
  args: { variant: 'standalone', children: 'Export match history' },
  globals: { viewport: { value: 'reviewWidthNarrow' } },
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

// structural-tier.md §9 "hover — ink `link-hover`, underline thickens to `border.ring`." Its own
// named story rather than only `RestAndHover`'s invitation above. `tests/visual/stories.spec.ts`
// drives the real `:hover` from Playwright once this story has settled (see that file's own
// `VisualForceState` comment) — a `play()` here could only dispatch a synthetic event, which the
// pseudo-class ignores.
export const Hover: Story = {
  args: { variant: 'standalone' },
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
}

// §9 "focus-visible — `outline-ring`... around the whole link box, on top of whatever the hover
// paint is. Never removed on pointer interaction."
export const FocusVisible: Story = {
  args: { variant: 'standalone' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'link' } },
}

// §9 "active — `standalone`: the hover paint plus a `surface-sunken` fill behind the link's box."
export const ActiveStandalone: Story = {
  args: { variant: 'standalone' },
  parameters: { visualForceState: { state: 'active', role: 'link' } },
}

// §9 "active — ... `inline`: the hover paint, with **no** fill — painting a wash behind three
// words inside a paragraph breaks the line — but the underline drops to `underline-offset-4`",
// distinguishing this frame from `Hover` above without one (fourth-pass review remediation,
// FR-037).
export const ActiveInline: Story = {
  render: (args) => (
    <p className="type-body max-w-measure text-md text-text-primary">
      Every match this profile has played is listed below. To link a different account,{' '}
      <Link {...args}>view its profile</Link> and choose "Link this account" instead.
    </p>
  ),
  parameters: { visualForceState: { state: 'active', role: 'link' } },
}

// §9 "disabled — a link is never disabled. A destination the reader may not reach renders as
// `Text` with a sentence saying why."
export const DisabledNotApplicable: Story = {
  render: () => (
    <p className="type-body text-md text-text-primary">
      This replay is past Microsoft's 31-day retention window, so nothing can retrieve it — a
      greyed-out link would be a promise this product could not keep.
    </p>
  ),
}

// §9 "loading — none... error — none of its own. A navigation that fails lands on a route that
// renders `ErrorState`."
export const LoadingErrorNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Navigation is the browser's own: a link never shows a loading spinner (that is a `Button`'s
        job), and it carries no error state of its own — a navigation that fails lands on a route
        that renders `ErrorState`.
      </p>
      <Link href="/players/1807091">View profile</Link>
    </div>
  ),
}
