import type { Meta, StoryObj } from '@storybook/react-vite'
import { within } from 'storybook/test'
import { Button } from '../Button'
import { Callout } from './index'

const meta: Meta<typeof Callout> = {
  title: 'Primitives/Callout',
  component: Callout,
}

export default meta
type Story = StoryObj<typeof Callout>

export const Info: Story = {
  args: {
    tone: 'info',
    heading: 'This Steam account has no Age of Empires II profile yet',
    children:
      'Your sign-in worked. The game creates a profile the first time you play a match online.',
    actions: (
      <>
        <Button variant="primary">Try again</Button>
        <Button variant="secondary">Use a different Steam account</Button>
      </>
    ),
  },
}

export const Success: Story = {
  args: {
    tone: 'success',
    heading: 'Archival is on.',
    children: 'We started with the last 31 days. New matches are picked up automatically.',
  },
}

export const Warning: Story = {
  args: {
    tone: 'warning',
    heading: 'These figures could not be refreshed',
    children:
      'Body text stays the primary text colour in every tone, so no tone has to carry normal-size body text on its own.',
    actions: <Button variant="primary">Try again</Button>,
  },
}

export const Danger: Story = {
  args: {
    tone: 'danger',
    heading: 'We could not verify that sign-in with Steam',
    children:
      'Steam did not confirm the response we received, so we did not sign you in. Start again from the beginning.',
    actions: <Button variant="primary">Start over</Button>,
  },
}

export const Empty: Story = {
  render: () => (
    <div>
      <p className="text-text-secondary text-sm">
        Nothing renders below this line — an empty callout is absent, not a blank box.
      </p>
      <Callout tone="info" heading="" />
    </div>
  ),
}

// shared-primitives.md §Callout "focus-visible": "when the callout receives programmatic focus
// (see sign-in-screen), the heading takes `tabindex=\"-1\"` and shows the standard focus ring" —
// forced here the same way a caller does it on mount, by focusing the heading directly rather than
// by tabbing (its `tabIndex={-1}` keeps it out of the normal tab sequence on purpose).
export const FocusVisible: Story = {
  args: {
    tone: 'info',
    heading: 'This Steam account has no Age of Empires II profile yet',
    children:
      'Your sign-in worked. The game creates a profile the first time you play a match online.',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    canvas.getByRole('heading').focus()
  },
}

// §Callout "hover / active — none; the root is not interactive. Actions inside it have their own."
export const HoverActiveNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A callout's own root is never interactive — no hover fill, no press feedback. The action
        buttons inside one carry their own hover and active states.
      </p>
      <Callout
        tone="info"
        heading="This Steam account has no Age of Empires II profile yet"
        actions={<Button variant="primary">Try again</Button>}
      >
        Your sign-in worked. The game creates a profile the first time you play a match online.
      </Callout>
    </div>
  ),
}

// §Callout "disabled — none; a callout is never disabled."
export const DisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A callout is never disabled — there is no dimmed or inert rendering of this component.
      </p>
      <Callout tone="info" heading="This Steam account has no Age of Empires II profile yet">
        Your sign-in worked. The game creates a profile the first time you play a match online.
      </Callout>
    </div>
  ),
}

// §Callout "loading — none; a callout describes a settled outcome. Anything still resolving is a
// `Skeleton`."
export const LoadingNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A callout describes a settled outcome. While the outcome is still resolving, the caller
      renders a `Skeleton` instead — a callout never appears mid-resolution.
    </p>
  ),
}
