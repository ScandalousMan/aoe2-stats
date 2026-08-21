import type { Meta, StoryObj } from '@storybook/react-vite'
import { StatValue } from './index'

const meta: Meta<typeof StatValue> = {
  title: 'Primitives/StatValue',
  component: StatValue,
}

export default meta
type Story = StoryObj<typeof StatValue>

export const Hero: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1842',
    delta: { value: 12 },
    secondaryLine: 'Measured 3 minutes ago',
  },
}

export const Compact: Story = {
  args: { variant: 'compact', label: 'Rank', value: '#214' },
}

export const Inline: Story = {
  args: { variant: 'inline', label: 'Win rate', value: '54%' },
}

export const NegativeDelta: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1802',
    delta: { value: -8 },
  },
}

export const Loading: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    status: 'loading',
    loadingWidthClassName: 'w-24',
  },
}

export const EmptyNeverObserved: Story = {
  args: {
    variant: 'compact',
    label: 'Rank',
    status: 'empty',
    secondaryLine: 'Not ranked yet',
  },
}

export const StaleAfterFailedRefresh: Story = {
  args: {
    variant: 'hero',
    label: '1v1 Random Map',
    value: '1842',
    secondaryLine: 'Measured 2 hours ago — refresh failed',
  },
}

export const StackedAlignment: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      <StatValue variant="hero" label="1v1 Random Map" value="1842" />
      <StatValue variant="hero" label="Team Random Map" value="128" />
      <StatValue variant="hero" label="4v4 Random Map" value="15" />
    </div>
  ),
}
