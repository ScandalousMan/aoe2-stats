import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { ArchivalControl } from './index'

const meta: Meta<typeof ArchivalControl> = {
  id: 'screens-archivalcontrol',
  title: 'Screens/Profile & capture/ArchivalControl',
  component: ArchivalControl,
  parameters: {
    docs: {
      description: {
        component: `Tells the user, in one place, that replays are archived by default and why, and gives them the one control that stops or resumes it.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof ArchivalControl>

// The four states T406 names: archiving (never answered), archiving (explicitly resumed),
// objected, and the write-failed state.

export const ArchivingNeverAnswered: Story = {
  name: 'Archiving — never answered',
  args: { state: 'archiving', onObject: () => {} },
}

export const ArchivingResumed: Story = {
  name: 'Archiving — explicitly resumed',
  args: { state: 'archiving', justResumed: true, onObject: () => {} },
}

export const Objected: Story = {
  args: { state: 'objected', objectedAt: 'on 12 August 2026', onResume: () => {} },
}

export const WriteFailed: Story = {
  name: 'Write failed',
  args: { state: 'archiving', writeFailed: true, onObject: () => {} },
}

// Supporting states the component checklist (design-system skill, "all states implemented") also
// requires stories for, beyond the four T406 names above.

export const Submitting: Story = {
  args: { state: 'archiving', submitting: true, onObject: () => {} },
}

export const Unavailable: Story = {
  args: { state: 'archiving', unavailable: true, onObject: () => {} },
}

// `loading: true` renders `Skeleton`, which stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  args: { loading: true },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

export const WithPrivacyNotice: Story = {
  name: 'With privacy notice link',
  args: {
    state: 'objected',
    objectedAt: 'on 12 August 2026',
    onResume: () => {},
    privacyNoticeHref: '/privacy',
  },
}

// archival-control.md §5 "hover / focus-visible / active — owned by `Button` and by the privacy
// link. The section itself is not interactive and shows no hover affordance." That claim is now
// true of the rendered link: §5.1 (T596, 2026-09-21) makes `PrivacyNoticeLink` the `Link` primitive
// at `variant="standalone"`, which paints real `hover:`/`focus-visible:`/`active:` classes, so
// `Hover`/`FocusVisible`/`Active` below actually depict it — this story no longer defers to a gap.
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        This section is not interactive and shows no hover affordance of its own — the switch button
        and the privacy link carry their own hover, focus and active states.
      </p>
      <ArchivalControl {...args} />
    </div>
  ),
  args: { state: 'archiving', onObject: () => {} },
}

// §5.1 "one `Hover`, one `FocusVisible` and one `Active` story, each forcing its state on
// `role: 'link'` named "Read the privacy notice" and each `visualCaptureClip`ped to that link (the
// standing rule for a signal smaller than roughly 1% of its own frame)." `name` is unambiguous:
// this is the only link this component ever renders.
const PRIVACY_LINK_CLIP = {
  parts: [{ role: 'link' as const, name: 'Read the privacy notice' }],
  pad: '2',
} as const

const withPrivacyNoticeArgs = {
  state: 'objected' as const,
  objectedAt: 'on 12 August 2026',
  onResume: () => {},
  privacyNoticeHref: '/privacy',
}

export const PrivacyNoticeLinkHover: Story = {
  name: 'hover on PrivacyNoticeLink ("Read the privacy notice")',
  args: withPrivacyNoticeArgs,
  parameters: {
    visualForceState: { state: 'hover', role: 'link', name: 'Read the privacy notice' },
    visualCaptureClip: PRIVACY_LINK_CLIP,
  },
}

export const PrivacyNoticeLinkFocusVisible: Story = {
  name: 'focus-visible on PrivacyNoticeLink ("Read the privacy notice")',
  args: withPrivacyNoticeArgs,
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link', name: 'Read the privacy notice' },
    visualCaptureClip: PRIVACY_LINK_CLIP,
  },
}

export const PrivacyNoticeLinkActive: Story = {
  name: 'active (pressed) on PrivacyNoticeLink ("Read the privacy notice")',
  args: withPrivacyNoticeArgs,
  parameters: {
    visualForceState: { state: 'active', role: 'link', name: 'Read the privacy notice' },
    visualCaptureClip: PRIVACY_LINK_CLIP,
  },
}

// §5 "empty — this component has no list and no collection to be empty. Its only content is the
// current archival status... there is no third 'nothing yet' fact for an empty state to
// represent."
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      This component has no list and no collection to be empty — its only content is the current
      archival status, which is always one of exactly two values.
    </p>
  ),
}
