import type { Meta, StoryObj } from '@storybook/react-vite'
import { Skeleton } from './index'

const meta: Meta<typeof Skeleton> = {
  title: 'Primitives/Skeleton',
  component: Skeleton,
}

export default meta
type Story = StoryObj<typeof Skeleton>

export const Text: Story = {
  args: { variant: 'text', lines: 3 },
}

export const NumberFootprint: Story = {
  args: { variant: 'number', className: 'h-9 w-24' },
}

export const Block: Story = {
  args: { variant: 'block', className: 'h-12 w-full' },
}

export const CombinedLoadingRegion: Story = {
  render: () => (
    <div aria-busy="true" className="flex flex-col gap-3">
      <Skeleton variant="text" lines={1} className="w-1/3" />
      <Skeleton variant="number" className="h-9 w-32" />
      <Skeleton variant="text" lines={2} />
    </div>
  ),
}
