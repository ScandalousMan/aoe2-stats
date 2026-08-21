import type { Meta, StoryObj } from '@storybook/react-vite'
import { ConsentStep } from './index'

const meta: Meta<typeof ConsentStep> = {
  title: 'Screens/ConsentStep',
  component: ConsentStep,
}

export default meta
type Story = StoryObj<typeof ConsentStep>

export const Onboarding: Story = {
  args: { variant: 'onboarding' },
}

export const OnboardingLoading: Story = {
  args: { variant: 'onboarding', submitting: true, submittingChoice: 'accept' },
}

export const OnboardingWriteFailed: Story = {
  args: { variant: 'onboarding', writeFailed: true },
}

export const SettingsUnanswered: Story = {
  args: { variant: 'settings', decision: 'unanswered' },
}

export const SettingsAccepted: Story = {
  args: {
    variant: 'settings',
    decision: 'accepted',
    recordedAt: '3 days ago',
    onTurnOffArchival: () => {},
  },
}

export const SettingsDeclined: Story = {
  args: { variant: 'settings', decision: 'declined' },
}

export const SettingsLoading: Story = {
  args: { variant: 'settings', loadingCurrentState: true },
}

// `visual-full-page` (scripts/visual/run.mjs): this variant renders a `position: fixed` dialog,
// which paints relative to the viewport rather than the story root — a screenshot clipped to that
// root captures neither the dialog nor the overlay behind it.
export const WithdrawConfirm: Story = {
  tags: ['visual-full-page'],
  args: { variant: 'withdraw-confirm', onConfirmWithdraw: () => {}, onCancelWithdraw: () => {} },
}
