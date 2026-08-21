import type { Meta, StoryObj } from '@storybook/react-vite'
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
