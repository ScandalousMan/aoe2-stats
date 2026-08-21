import type { Meta, StoryObj } from '@storybook/react-vite'
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
      'Body text stays the primary text colour even in the warning tone, which is the one deliberately below the normal-text contrast floor.',
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
