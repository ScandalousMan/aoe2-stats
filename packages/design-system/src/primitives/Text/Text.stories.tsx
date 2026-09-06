import type { Meta, StoryObj } from '@storybook/react-vite'
import { Text } from './index'

const meta: Meta<typeof Text> = {
  title: 'Primitives/Text',
  component: Text,
  args: {
    role: 'body',
    children: 'Every match this profile has played, most recent first.',
  },
}

export default meta
type Story = StoryObj<typeof Text>

export const Display: Story = {
  args: { role: 'display', children: 'Recent matches' },
}

export const Body: Story = {
  args: { role: 'body', children: 'Every match this profile has played, most recent first.' },
}

export const Supporting: Story = {
  args: { role: 'supporting', children: 'Checked 3 minutes ago.' },
}

export const Numeric: Story = {
  args: { role: 'numeric', children: '1204' },
}

export const Machine: Story = {
  args: { role: 'machine', children: 'replay_parse_failed' },
}

export const Identifier: Story = {
  args: { role: 'identifier', children: '1807091' },
}

// §8's specimen acceptance criterion: all six roles at once, and specifically `numeric`,
// `machine` and `identifier` distinguishable from one another — the split DS-8 existed to make.
export const AllRoles: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      <Text role="display">Recent matches</Text>
      <Text role="body">Every match this profile has played, most recent first.</Text>
      <Text role="supporting">Checked 3 minutes ago.</Text>
      <Text role="numeric">1204</Text>
      <Text role="machine">replay_parse_failed</Text>
      <Text role="identifier">1807091</Text>
    </div>
  ),
}

// §8's alignment acceptance criterion: a column of differing digit counts aligns digit-for-digit
// through `tabular-nums`, independent of the monospace family (SC-009). The right edge is a
// straight line regardless of how many digits each row has.
export const NumericAlignment: Story = {
  render: () => (
    <div className="flex flex-col items-end">
      <Text role="numeric">1</Text>
      <Text role="numeric">42</Text>
      <Text role="numeric">1204</Text>
      <Text role="numeric">98765</Text>
    </div>
  ),
}

// `display`'s heading level is chosen by the caller (`Page`/`Section` in practice) via `as`; the
// size step does not change with the level — one size per role, stated once in §8.
export const HeadingLevels: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <Text role="display" as="h1">
        Heading level 1
      </Text>
      <Text role="display" as="h2">
        Heading level 2
      </Text>
      <Text role="display" as="h3">
        Heading level 3
      </Text>
    </div>
  ),
}

// A page composed of `display`, `body` and `supporting` should show three clear levels of
// hierarchy at a glance (FR-063) — the criterion a token-correct implementation that used `body`
// for a heading would fail.
export const Hierarchy: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <Text role="display">Match history</Text>
      <Text role="body">Every match this profile has played, most recent first.</Text>
      <Text role="supporting">42 matches across the last 30 days.</Text>
    </div>
  ),
}

// §8 "empty": no children renders nothing at all — not an empty paragraph occupying a line box.
export const Empty: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The text below has no children and renders nothing — no line box, no placeholder.
      </p>
      <Text role="body">{''}</Text>
    </div>
  ),
}
