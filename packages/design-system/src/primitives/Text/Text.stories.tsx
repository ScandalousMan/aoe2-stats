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

// structural-tier.md §8 "hover / active — none. Text is not a control. Text that responds to a
// pointer is a `Link` or sits inside a `Button`."
export const HoverActiveNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Text is not a control — no hover or active rendering of its own. Text that responds to a
        pointer is a `Link` or sits inside a `Button`.
      </p>
      <Text role="body">Every match this profile has played, most recent first.</Text>
    </div>
  ),
}

// §8 "focus-visible — none of its own. `Text` is not focusable; a heading that receives
// programmatic focus... takes `tabIndex={-1}` from its caller and shows the standard ring against
// the surface it sits on."
export const FocusVisibleNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Text is not focusable on its own. A heading that receives programmatic focus takes
        `tabIndex={-1}` from its caller and shows the standard ring — that ring belongs to the
        caller, not to this component.
      </p>
      <Text role="display">Recent matches</Text>
    </div>
  ),
}

// §8 "disabled — `Text` never paints `text-disabled`. Disabled ink belongs to a disabled control's
// own label; de-emphasised standing text is `text-secondary`."
export const DisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Text never paints the disabled ink — that belongs to a disabled control's own label.
        De-emphasised standing text uses the `supporting` role's `text-secondary` instead.
      </p>
      <Text role="supporting">Checked 3 minutes ago.</Text>
    </div>
  ),
}

// §8 "loading — `Text` renders no placeholder. No dash, no ellipsis, no zero: a value that has not
// arrived is a `Skeleton` in the caller's hands."
export const LoadingNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      Text renders no placeholder for arriving content — no dash, no ellipsis, no zero. A value that
      has not arrived is a `Skeleton` in the caller's hands, never a rendering of this component.
    </p>
  ),
}

// §8 "error — none. `Text` never colours itself `danger`. A failure has a component (`Field`'s
// error line, `ErrorState`, `Callout`); text that turns red on its own is a failure with no owner."
export const ErrorNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Text never colours itself `danger` on its own. A failure has a component that owns it —
        `Field`'s error line, `ErrorState`, `Callout` — never a red-tinted paragraph with no owner.
      </p>
      <Text role="body">Every match this profile has played, most recent first.</Text>
    </div>
  ),
}
