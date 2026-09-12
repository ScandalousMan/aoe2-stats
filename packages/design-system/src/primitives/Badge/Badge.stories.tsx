import type { Meta, StoryObj } from '@storybook/react-vite'
import { Badge } from './index'

const meta: Meta<typeof Badge> = {
  id: 'primitives-badge',
  title: 'Primitives/Feedback & status/Badge',
  component: Badge,
  parameters: {
    docs: {
      description: {
        component: `Marks one item in a list as being in a named state, at a glance.`,
      },
    },
  },
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

// shared-primitives.md §Badge "empty — a badge with no label renders nothing."
export const Empty: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Nothing renders below this line — a badge with no label is absent, not a blank pill.
      </p>
      <Badge variant="neutral">{''}</Badge>
    </div>
  ),
}

// §Badge "default only. No hover, no active, no focus: a badge is not interactive and must never
// be the control that changes the state it names."
export const HoverFocusActiveNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A badge is not interactive: no hover, focus or active state, and it is never itself the
        control that changes the state it names.
      </p>
      <Badge variant="neutral">Not ranked yet</Badge>
    </div>
  ),
}

// §Badge "disabled / loading — none; during a state change the badge is replaced by a `Skeleton`
// of the same footprint."
export const DisabledLoadingNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A badge has no disabled or loading rendering of its own — while the state it names is
      changing, the caller replaces it with a `Skeleton` of the same footprint instead.
    </p>
  ),
}

// §Badge "error — none."
export const ErrorNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A badge carries no error state of its own — a failure belongs to whatever produced the state
      it names, never to the badge.
    </p>
  ),
}
