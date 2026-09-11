import type { Meta, StoryObj } from '@storybook/react-vite'
import { AccountErasurePanel, ErasedScreen } from './index'

const meta: Meta<typeof AccountErasurePanel> = {
  id: 'screens-accounterasurepanel',
  title: 'Screens/Account & privacy/AccountErasurePanel',
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

// privacy-data-rights.md §5 "loading — ... `minting` shows the `EraseButton` busy while the token
// is fetched" — the phase before the dialog opens, distinct from `erasing` below.
export const Minting: Story = {
  name: 'minting — the erase button busy while the confirmation token is fetched',
  args: { ...noopHandlers, initialState: 'minting' },
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

// privacy-data-rights.md §5 "hover / focus-visible / active — owned by the `Button`s, the
// `Dialog`'s actions and the `Acknowledgement` checkbox; the sections themselves are not
// interactive."
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The panel's own sections are not interactive — hover, focus and active belong to the
        buttons, the dialog's actions and the acknowledgement checkbox, each already covered by
        their own components' stories.
      </p>
      <AccountErasurePanel {...args} />
    </div>
  ),
  args: { ...noopHandlers, initialState: 'idle' },
}

// §5 "empty — not applicable — it is a single irreversible action, not a collection; there is no
// 'nothing yet' fact for an empty state to represent, and this is stated rather than omitted."
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      This is a single irreversible action, not a collection — there is no "nothing yet" fact for an
      empty state to represent.
    </p>
  ),
}
