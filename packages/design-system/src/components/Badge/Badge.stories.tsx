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

export const Success: Story = {
  args: { variant: 'success', children: 'Archived' },
}

export const Warning: Story = {
  args: { variant: 'warning', children: 'Still catchable' },
}

export const Danger: Story = {
  args: { variant: 'danger', children: 'Lost' },
}

export const Info: Story = {
  args: { variant: 'info', children: 'Needs review' },
}

// capture-state-badge.md acceptance: all four tones distinct from each other and from
// `neutral`/`accent`, in the same screenshot.
export const AllTones: Story = {
  render: () => (
    <ul className="flex flex-col gap-2">
      <li className="flex items-center gap-2">
        <Badge variant="neutral">Neutral</Badge>
      </li>
      <li className="flex items-center gap-2">
        <Badge variant="accent">Accent</Badge>
      </li>
      <li className="flex items-center gap-2">
        <Badge variant="success">Archived</Badge>
      </li>
      <li className="flex items-center gap-2">
        <Badge variant="warning">Still catchable</Badge>
      </li>
      <li className="flex items-center gap-2">
        <Badge variant="danger">Lost</Badge>
      </li>
      <li className="flex items-center gap-2">
        <Badge variant="info">Needs review</Badge>
      </li>
    </ul>
  ),
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
