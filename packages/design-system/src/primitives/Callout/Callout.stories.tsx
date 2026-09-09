import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../Button'
import { Callout } from './index'

const meta: Meta<typeof Callout> = {
  id: 'primitives-callout',
  title: 'Primitives/Feedback & status/Callout',
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

// shared-primitives.md §Callout "focus-visible": the heading is `tabindex="-1"` and paints
// `outline-none` — its focus is for the accessible-name announcement, not a visible indicator
// (the same shape `Dialog`'s heading owns). Remediation (fifth-pass review M1): this story used to
// force focus onto the heading and stop there, which shows nothing — six baselines with zero
// focus-ring pixels, standing in for a state that has no visual form of its own. Repointed the same
// way `Dialog`'s own `FocusVisible` story was: `visualForceState` drives real focus onto the next
// stop after the heading, `primaryAction` here (rendered first in the action row, `index.tsx`'s own
// order) — a real `Button`, carrying a real ring, and a real "what happens when you tab past this
// heading" answer rather than a frame that documents nothing.
export const FocusVisible: Story = {
  args: {
    tone: 'info',
    heading: 'This Steam account has no Age of Empires II profile yet',
    children:
      'Your sign-in worked. The game creates a profile the first time you play a match online.',
    actions: <Button variant="primary">Try again</Button>,
  },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button', name: 'Try again' },
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
