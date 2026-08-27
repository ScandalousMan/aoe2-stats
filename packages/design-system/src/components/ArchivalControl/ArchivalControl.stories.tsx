import type { Meta, StoryObj } from '@storybook/react-vite'
import { ArchivalControl } from './index'

const meta: Meta<typeof ArchivalControl> = {
  title: 'Screens/ArchivalControl',
  component: ArchivalControl,
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

export const Loading: Story = {
  args: { loading: true },
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
