import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { Callout } from '../Callout'
import { Button } from './index'

const meta: Meta<typeof Button> = {
  title: 'Primitives/Button',
  component: Button,
  args: {
    children: 'Continue with Steam',
  },
}

export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: { variant: 'primary', size: 'lg' },
}

export const Secondary: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
}

export const Ghost: Story = {
  args: { variant: 'ghost', children: 'Manage' },
}

export const Destructive: Story = {
  args: { variant: 'destructive', children: 'Unlink this profile' },
}

export const Loading: Story = {
  args: { variant: 'primary', size: 'lg', loading: true, loadingLabel: 'Taking you to Steam…' },
}

export const Disabled: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-2">
      <Button variant="primary" size="lg" disabled>
        Continue with Steam
      </Button>
      <p className="text-text-secondary text-sm">Sign-in is not configured right now.</p>
    </div>
  ),
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}

export const AsLink: Story = {
  args: { variant: 'secondary', href: '#', children: 'Read the privacy notice' },
}

// shared-primitives.md §Button "hover": fill deepens to `accent-hover`, colour only — a still
// capture of the real `:hover` pseudo-class, forced here because Storybook cannot force it from
// controls alone.
export const Hover: Story = {
  args: { variant: 'primary', size: 'lg' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.hover(canvas.getByRole('button'))
  },
}

// §Button "focus-visible": the standard ring, reached by the keyboard only — never by a pointer
// click (that is what makes it `:focus-visible` rather than `:focus`).
export const FocusVisible: Story = {
  args: { variant: 'primary', size: 'lg' },
  play: async () => {
    await userEvent.tab()
  },
}

// §Button "active": `accent-active`, the third of three deliberately distinct fills (rest, hover,
// press) — held down rather than released so the capture shows the pressed frame.
export const Active: Story = {
  args: { variant: 'primary', size: 'lg' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const button = canvas.getByRole('button')
    await userEvent.pointer({ keys: '[MouseLeft>]', target: button })
  },
}

// §Button "error": "the button has no error state of its own. The failure renders in a `Callout`
// beside or above it and the button returns to `default` and to being pressable" — shown here
// rather than only described, so the answer is a picture rather than a sentence to trust.
export const ErrorNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      <Callout tone="danger" heading="We could not verify that sign-in with Steam">
        Steam did not confirm the response we received, so we did not sign you in. Start again from
        the beginning.
      </Callout>
      <Button variant="primary" size="lg">
        Continue with Steam
      </Button>
    </div>
  ),
}

// §Button "empty": "not applicable: a button with no label is invalid" — there is no rendering to
// show, so the answer is words rather than a blank button.
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A `Button` with no label is invalid — there is no icon-only form on the primary path of any
      screen in this feature, so this state has no rendering to show.
    </p>
  ),
}
