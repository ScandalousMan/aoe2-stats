import type { Meta, StoryObj } from '@storybook/react-vite'
import { AccountErasurePanel, ErasedScreen } from './index'

const meta: Meta<typeof AccountErasurePanel> = {
  title: 'Screens/AccountErasurePanel',
  component: AccountErasurePanel,
}

export default meta
type Story = StoryObj<typeof AccountErasurePanel>

// `initialState` renders one fixed frame without driving real promises (privacy-data-rights.md
// §3) — the callbacks below are never actually exercised by these stories.
const noopHandlers = {
  onRequestConfirmation: () => new Promise<{ confirmationToken: string }>(() => {}),
  onErase: () => new Promise<void>(() => {}),
}

export const Idle: Story = {
  name: 'default — the irreversible lede and both consequence groups, before any dialog',
  args: { ...noopHandlers, initialState: 'idle' },
}

export const Confirming: Story = {
  name: 'confirming — the dialog open, checkbox unchecked, confirm disabled',
  args: { ...noopHandlers, initialState: 'confirming' },
}

export const ConfirmationExpired: Story = {
  name: 'confirmation expired — the 403 from POST, offering to confirm again',
  args: { ...noopHandlers, initialState: 'confirmation-expired' },
}

export const Failed: Story = {
  name: 'failed — the dialog stays open, confirm re-enabled, nothing erased',
  args: { ...noopHandlers, initialState: 'failed' },
}

export const Erasing: Story = {
  name: 'erasing — the POST in flight, confirm busy, cancel disabled',
  args: { ...noopHandlers, initialState: 'erasing' },
}

export const Erased: Story = {
  name: 'terminal — ErasedScreen, no "sign back in" affordance',
  render: () => <ErasedScreen homeHref="/privacy-notice" />,
}
