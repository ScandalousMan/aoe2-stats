import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { Skeleton } from './index'

const meta: Meta<typeof Skeleton> = {
  id: 'primitives-skeleton',
  title: 'Primitives/Feedback & status/Skeleton',
  component: Skeleton,
  parameters: {
    docs: {
      description: {
        component: `Holds the shape of content that is arriving, so nothing jumps when it lands.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof Skeleton>

// `Skeleton` renders nothing for the first `duration.normal` (200ms, `useDelayedVisible` in
// `lib/`) so a load that resolves quickly never flashes a pulse — a `setTimeout`, not a wall
// clock, but a clock all the same (T568, FR-047): a screenshot fired before that timer resolves
// catches the pre-visible, empty frame; one fired after catches the pulse; which one happens is a
// race against however long Storybook took to mount this particular story, not a state the story
// declares. Waiting here for the pulse element to actually exist — rather than a fixed sleep —
// holds regardless of machine speed and survives `useDelayedVisible`'s own delay changing later.
async function waitForPulse({ canvasElement }: { canvasElement: HTMLElement }) {
  await waitFor(() => {
    expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
  })
}

export const Text: Story = {
  args: { variant: 'text', lines: 3 },
  play: waitForPulse,
}

export const NumberFootprint: Story = {
  args: { variant: 'number', className: 'h-9 w-24' },
  play: waitForPulse,
}

export const Block: Story = {
  args: { variant: 'block', className: 'h-12 w-full' },
  play: waitForPulse,
}

export const CombinedLoadingRegion: Story = {
  render: () => (
    <div aria-busy="true" className="flex flex-col gap-3">
      <Skeleton variant="text" lines={1} className="w-1/3" />
      <Skeleton variant="number" className="h-9 w-32" />
      <Skeleton variant="text" lines={2} />
    </div>
  ),
  play: waitForPulse,
}

// shared-primitives.md §Skeleton "empty — a skeleton with a zero count renders nothing."
export const Empty: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Nothing renders below this line — a skeleton asked for zero lines is absent, not a
        zero-height pulse.
      </p>
      <Skeleton variant="text" lines={0} />
    </div>
  ),
}

// FR-055/SC-016: the pulse below is the real `animate-pulse` utility, gated by Tailwind's
// `motion-safe:` variant (`motion.json`'s `animation.pulse`, T516/T528) — under `prefers-reduced-
// motion: reduce` the utility does not apply at all, and what is left is this static block at its
// own resting frame, never a paused mid-pulse one (README rule 5). No mechanism here can force that
// browser preference for an automated capture (`.storybook/foundations/Motion.stories.tsx` names
// the same limit for the same reason) — toggle "Emulate CSS media feature prefers-reduced-motion"
// in the browser's dev tools to see the block below settle on exactly this frame, live.
export const ReducedMotionRestingFrame: Story = {
  name: 'Reduced motion — resting frame, no perceptible animation (FR-055)',
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Toggle your browser's reduced-motion emulation to see the block below stop pulsing and
        settle on this frame — the same static state a reader with the OS preference set sees from
        the very first paint.
      </p>
      <Skeleton variant="block" className="h-12 w-full" />
    </div>
  ),
  play: waitForPulse,
}

// §Skeleton "loading is the only state the component exists for. It has no hover, focus, active,
// disabled or error state."
export const HoverFocusActiveDisabledErrorNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Loading is the only state a skeleton has — no hover, focus, active, disabled or error
        rendering exists for it.
      </p>
      <Skeleton variant="block" className="h-12 w-full" />
    </div>
  ),
  play: waitForPulse,
}
