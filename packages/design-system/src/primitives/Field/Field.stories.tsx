import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { Button } from '../Button'
import { Field } from './index'

const meta: Meta<typeof Field> = {
  title: 'Primitives/Field',
  component: Field,
}

export default meta
type Story = StoryObj<typeof Field>

// A demonstration `<input>` styled directly from the token vocabulary (contracts/005-design-system-
// foundations/token-families.md §2). `Field` does not paint the control — that stays the caller's,
// per structural-tier.md §11's anatomy — so every story below supplies one, the same way a real
// route would. `invalid` is plain conditional logic driven by the same boolean the story already
// has in scope, not a CSS attribute selector, so a story never depends on anything beyond React
// props to render correctly.
function DemoInput({
  invalid,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      {...rest}
      className={
        'w-full rounded-control border bg-surface px-3 type-body text-sm text-text-primary ' +
        'transition-colors duration-120 ease-standard motion-reduce:duration-0 outline-none ' +
        'focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring ' +
        'disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-disabled disabled:border-border ' +
        (invalid ? 'border-danger' : 'border-border-strong')
      }
    />
  )
}

export const Default: Story = {
  args: {
    label: 'Display name',
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
}

export const WithHint: Story = {
  args: {
    label: 'Your Age of Empires II profile id',
    hint: 'The number in the address of a player’s profile page — the only thing this form asks for.',
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput inputMode="numeric" />
      </Field>
    </div>
  ),
}

export const Error: Story = {
  args: {
    label: 'Your Age of Empires II profile id',
    hint: 'The number in the address of a player’s profile page.',
    error: 'Profile id — enter digits only.',
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput inputMode="numeric" defaultValue="abc" invalid />
      </Field>
    </div>
  ),
}

export const Disabled: Story = {
  args: {
    label: 'Display name',
    hint: 'Locked while your Steam account is linked — unlink it first to change this.',
    disabled: true,
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput defaultValue="TheViper" />
      </Field>
    </div>
  ),
}

export const Loading: Story = {
  args: {
    label: 'Your Age of Empires II profile id',
    hint: 'The number in the address of a player’s profile page.',
    loading: true,
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput inputMode="numeric" defaultValue="199325" />
      </Field>
    </div>
  ),
}

export const LabelHidden: Story = {
  name: 'Label hidden (adjacent visible label)',
  args: {
    label: 'Search for a player',
    labelHidden: true,
  },
  render: (args) => (
    <div className="flex max-w-sm items-end gap-2">
      <div className="flex-1">
        <Field {...args}>
          <DemoInput placeholder="Search for a player" />
        </Field>
      </div>
      <Button variant="primary" size="md">
        Search
      </Button>
    </div>
  ),
}

export const SizeLg: Story = {
  name: 'Size — lg (touch)',
  args: {
    label: 'Display name',
    size: 'lg',
  },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
}

// The error's announcement is a *transition*: absent at Field's first render, then appearing —
// never present already at mount, which would double the page's own initial announcement
// (FR-053). This story reproduces exactly that transition rather than only its resting frame, the
// same way `tests/visual/focus-ring.spec.ts` is the shipping precedent for a state a static capture
// cannot show (structural-tier.md §0). `Field.test.tsx` asserts the underlying `role="alert"`
// mechanics; this is the story a person drives by hand from Storybook's own controls.
export const ErrorAppearsAfterMount: Story = {
  name: 'Error appears after mount (announced)',
  render: () => {
    function Demo() {
      const [touched, setTouched] = useState(false)
      const invalid = touched
      return (
        <div className="flex max-w-xs flex-col gap-3">
          <Field
            label="Your Age of Empires II profile id"
            hint="The number in the address of a player’s profile page."
            error={invalid ? 'Profile id — enter digits only.' : undefined}
          >
            <DemoInput inputMode="numeric" invalid={invalid} />
          </Field>
          <Button variant="secondary" size="md" onClick={() => setTouched(true)}>
            Trigger the error (simulates blur/submit validation)
          </Button>
        </div>
      )
    }
    return <Demo />
  },
}

export const RealisticForm: Story = {
  name: 'Realistic composition — a two-field form',
  render: () => (
    <form className="flex max-w-xs flex-col gap-4">
      <Field label="Display name" hint="Shown on your public profile.">
        <DemoInput defaultValue="TheViper" />
      </Field>
      <Field
        label="Steam profile URL"
        error="Steam profile URL — must start with https://steamcommunity.com/."
      >
        <DemoInput defaultValue="not-a-url" invalid />
      </Field>
      <div>
        <Button type="submit" variant="primary" size="md">
          Save
        </Button>
      </div>
    </form>
  ),
}
