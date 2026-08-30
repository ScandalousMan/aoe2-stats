import type { Meta, StoryObj } from '@storybook/react-vite'
import { Footer } from './index'

const meta: Meta<typeof Footer> = {
  title: 'Composite/Footer',
  component: Footer,
}

export default meta
type Story = StoryObj<typeof Footer>

// footer.md §5's states: the disclaimer and affiliation note never change; only LinkRow's
// membership does, driven entirely by which href props are supplied.

export const NoLinks: Story = {
  name: 'no links — disclaimer only, the state before T098a wires any route',
  args: {},
}

export const BothLinks: Story = {
  name: 'both links — privacy notice and the third-party objection form',
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
}

export const PrivacyNoticeOnly: Story = {
  name: 'privacy notice link only',
  args: { privacyNoticeHref: '/privacy-notice' },
}

export const ObjectionOnly: Story = {
  name: 'objection link only',
  args: { objectionHref: '/object' },
}
