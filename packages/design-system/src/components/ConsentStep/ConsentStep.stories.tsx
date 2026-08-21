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
  args: { variant: 'settings', decision: 'accepted', recordedAt: '3 days ago' },
}

export const SettingsDeclined: Story = {
  args: { variant: 'settings', decision: 'declined' },
}

export const SettingsLoading: Story = {
  args: { variant: 'settings', loadingCurrentState: true },
}

export const WithdrawConfirm: Story = {
  args: { variant: 'withdraw-confirm' },
}
