import type { Meta, StoryObj } from '@storybook/react-vite'
import { Skeleton } from '../Skeleton'
import { PlayerAvatar } from './index'

const meta: Meta<typeof PlayerAvatar> = {
  title: 'Composite/PlayerAvatar',
  component: PlayerAvatar,
}

export default meta
type Story = StoryObj<typeof PlayerAvatar>

// A fixture hash — the visual test runner stubs the CDN request this URL resolves to (§9's "the
// visual baseline must not depend on Steam"), never a real Steam hash. This story never makes a
// real network request from the test runner: `tests/visual/stories.spec.ts` fulfils
// `https://avatars.steamstatic.com/**` from a local fixture file.
const FIXTURE_HASH = '0123456789abcdef0123456789abcdef01234567'

export const Loaded: Story = {
  name: 'Loaded (network stubbed by the visual test runner — see tests/visual/stories.spec.ts)',
  args: { avatarHash: FIXTURE_HASH },
}

export const SizeSm: Story = {
  name: 'Size — sm (32px, ProfileSummary compact)',
  args: { avatarHash: FIXTURE_HASH, size: 'sm' },
}

export const SizeMd: Story = {
  name: 'Size — md (64px, default, ProfileSummary board identity bar)',
  args: { avatarHash: FIXTURE_HASH, size: 'md' },
}

export const BothSizes: Story = {
  name: 'Both sizes in one frame',
  render: () => (
    <div className="flex items-center gap-6">
      <PlayerAvatar avatarHash={FIXTURE_HASH} size="sm" />
      <PlayerAvatar avatarHash={FIXTURE_HASH} size="md" />
    </div>
  ),
}

// §4 "empty" — no hash at all: a legitimate resting state (a profile the companion never saw), not
// a degraded one. Must be pixel-identical to FailedHash below — the identity FR-008a reduces to.
export const AbsentHash: Story = {
  name: 'Empty — no hash at all (must render identically to the failed story below)',
  args: { avatarHash: undefined },
}

export const NullHash: Story = {
  name: 'Empty — avatarHash null',
  args: { avatarHash: null },
}

// §4 "error" — the hash resolves to a URL but the image fails to load or decode. `onError` removes
// the `<img>`, leaving frame and fill: byte-identical to AbsentHash above.
export const FailedHash: Story = {
  name: 'Error — hash fails to load (must render identically to the empty story above)',
  args: { avatarHash: 'does-not-resolve-on-the-cdn' },
}

// §4 "loading" (first wait) — the caller draws Skeleton/block at the avatar's exact footprint
// while the profile data has not arrived; this component is not rendered at all in that wait.
export const Loading: Story = {
  name: 'Loading (caller-rendered Skeleton/block, not a state of this component)',
  render: () => <Skeleton variant="block" className="h-16 w-16 rounded-md" />,
}

// Acceptance: loaded, absent and failed avatars, each beside the heading it always sits next to —
// the avatar never changes width between states, and the heading stays at the same x-position.
export const BesideAHeading: Story = {
  name: 'Beside a heading — footprint stays identical across states',
  render: () => (
    <ul className="flex flex-col gap-4">
      <li className="flex items-center gap-4">
        <PlayerAvatar avatarHash={FIXTURE_HASH} />
        <span className="font-sans text-lg font-semibold text-text-primary">GL.TheViper</span>
      </li>
      <li className="flex items-center gap-4">
        <PlayerAvatar avatarHash={undefined} />
        <span className="font-sans text-lg font-semibold text-text-primary">1807091</span>
      </li>
      <li className="flex items-center gap-4">
        <PlayerAvatar avatarHash="does-not-resolve-on-the-cdn" />
        <span className="font-sans text-lg font-semibold text-text-primary">Hera</span>
      </li>
    </ul>
  ),
}
