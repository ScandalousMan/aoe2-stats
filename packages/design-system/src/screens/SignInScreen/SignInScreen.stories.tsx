import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { SignInScreen } from './index'

const meta: Meta<typeof SignInScreen> = {
  id: 'screens-signinscreen',
  title: 'Screens/Account & privacy/SignInScreen',
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

// `phase: 'returning'` renders `Skeleton`, which stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving check never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Returning: Story = {
  args: { phase: 'returning' },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
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

// sign-in-screen.md §4 "hover / focus-visible / active — owned entirely by `Button`. The panel
// itself has no hover affordance and does not lift, glow or change fill: it is not a control."
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The panel itself has no hover, focus or active rendering of its own — it is not a control.
        Its "Continue with Steam" button carries its own, per `Button`'s stories.
      </p>
      <SignInScreen {...args} />
    </div>
  ),
}
