import type { Meta, StoryObj } from '@storybook/react-vite'
import { Badge } from './index'

const meta: Meta<typeof Badge> = {
  title: 'Primitives/Badge',
  component: Badge,
}

export default meta
type Story = StoryObj<typeof Badge>

export const Neutral: Story = {
  args: { variant: 'neutral', children: 'Not ranked yet' },
}

export const Accent: Story = {
  args: { variant: 'accent', children: 'Primary' },
}

export const InAList: Story = {
  render: () => (
    <ul className="flex flex-col gap-2">
      <li className="flex items-center gap-2">
        aoe2guy <Badge variant="accent">Primary</Badge>
      </li>
      <li className="flex items-center gap-2">
        aoe2alt <Badge variant="neutral">Provisional</Badge>
      </li>
    </ul>
  ),
}
