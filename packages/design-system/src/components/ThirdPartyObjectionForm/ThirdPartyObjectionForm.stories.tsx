import type { Meta, StoryObj } from '@storybook/react-vite'
import { ThirdPartyObjectionForm } from './index'

const meta: Meta<typeof ThirdPartyObjectionForm> = {
  title: 'Screens/ThirdPartyObjectionForm',
  component: ThirdPartyObjectionForm,
}

export default meta
type Story = StoryObj<typeof ThirdPartyObjectionForm>

// `initialState` renders one fixed frame without driving a real promise (third-party-objection.md
// §3) — `onSubmit` below is never actually exercised by these stories.
const noopHandlers = {
  onSubmit: () => new Promise<void>(() => {}),
  privacyNoticeHref: '/privacy-notice',
}

export const Idle: Story = {
  name: 'default — explanation above an empty, enabled field',
  args: { ...noopHandlers, initialState: 'idle' },
}

export const Submitting: Story = {
  name: 'submitting — busy button, same width as at rest, field read-only',
  args: { ...noopHandlers, initialState: 'submitting' },
}

export const Recorded: Story = {
  name: 'recorded — success callout; nothing claims data was already changed',
  args: { ...noopHandlers, initialState: 'recorded' },
}

export const RateLimited: Story = {
  name: 'rate-limited — warning callout, try-again message, button present',
  args: { ...noopHandlers, initialState: 'rate-limited' },
}

export const Failed: Story = {
  name: 'failed — danger callout, nothing recorded, button enabled again',
  args: { ...noopHandlers, initialState: 'failed' },
}
