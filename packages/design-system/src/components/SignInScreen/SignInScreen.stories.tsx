import type { Meta, StoryObj } from '@storybook/react-vite'
import { SignInScreen } from './index'

const meta: Meta<typeof SignInScreen> = {
  title: 'Screens/SignInScreen',
  component: SignInScreen,
  args: {
    onContinueWithSteam: () => {},
  },
}

export default meta
type Story = StoryObj<typeof SignInScreen>

export const Default: Story = {}

export const Link: Story = {
  args: { variant: 'link', onCancel: () => {} },
}

export const Leaving: Story = {
  args: { phase: 'leaving' },
}

export const Returning: Story = {
  args: { phase: 'returning' },
}

export const Unavailable: Story = {
  args: {
    phase: 'unavailable',
    unavailableMessage: 'Sign-in will be back shortly. Please try again in a few minutes.',
  },
}

export const NoAoe2Profile: Story = {
  args: { outcome: 'no_aoe2_profile' },
}

export const NotAllowlistedWithoutRequestRoute: Story = {
  args: { outcome: 'not_allowlisted' },
}

export const NotAllowlistedWithRequestRoute: Story = {
  args: { outcome: 'not_allowlisted', requestAccessHref: '#request-access' },
}

export const SteamAssertionInvalid: Story = {
  args: { outcome: 'steam_assertion_invalid' },
}

export const Unreachable: Story = {
  args: { outcome: 'unreachable' },
}

export const ProfileAlreadyLinked: Story = {
  args: { variant: 'link', outcome: 'profile_already_linked', onCancel: () => {} },
}
