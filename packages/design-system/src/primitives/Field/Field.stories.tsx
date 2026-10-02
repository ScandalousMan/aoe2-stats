import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { Button } from '../Button'
import { cx } from '../../lib/cx'
import { Field } from './index'

const meta: Meta<typeof Field> = {
  id: 'primitives-field',
  title: 'Primitives/Forms/Field',
  component: Field,
  parameters: {
    docs: {
      description: {
        component: `Puts a control, its label, its hint and its error together so they cannot come apart.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof Field>

// A demonstration `<input>` styled directly from the token vocabulary (contracts/005-design-system-
// foundations/token-families.md §2). `Field` does not paint the control — that stays the caller's,
// per structural-tier.md §11's anatomy — so every story below supplies one, the same way a real
// route would. `invalid` is plain conditional logic driven by the same boolean the story already
// has in scope, not a CSS attribute selector, so a story never depends on anything beyond React
// props to render correctly.
//
// §11.2 (structural-tier.md, decided 2026-09-28): the boundary thickens inward on hover, from
// `border.hairline` to `border.ring`, in `border-strong` (`danger` while invalid) — a `ring-1
// ring-inset` painted inside the permanent 1px border, scoped to an enabled control
// (`enabled:hover:`) so the rate-limit-disabled shape never thickens. The `hover:bg-surface-sunken`
// fill this demo used to carry (T565 remediation) is withdrawn: it is also the disabled fill, and
// the sweep measured it at zero surviving pixels regardless (`structural-tier.md` §16.2) — the ring is the real signal now, not a second one riding beside the old fill.
// Its own `FocusVisible` story stays undistinguished from `Default` for an unrelated, pre-existing
// reason this fix does not touch: `focus-visible:outline-ring`/`outline-offset-ring` set only the
// outline's width and offset, never `outline-style`, so the ring these classes name never paints
// regardless of how genuinely `:focus-visible` matches — that is a token/utility defect
// (`tokens/generated/preset.css`'s `@utility outline-ring`) shared with `Link` and `Table`, out of
// this remediation's scope (no `index.tsx` or `tokens/` edits here), and reported rather than
// papered over with a duplicate baseline.
function DemoInput({
  invalid,
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      {...rest}
      className={cx(
        'w-full rounded-control border bg-surface px-3 type-body text-sm text-text-primary ' +
          'transition-colors duration-120 ease-standard motion-reduce:duration-0 outline-none ' +
          'focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring ' +
          'disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-disabled disabled:border-border ' +
          (invalid
            ? 'border-danger enabled:hover:ring-1 enabled:hover:ring-inset enabled:hover:ring-danger'
            : 'border-border-strong enabled:hover:ring-1 enabled:hover:ring-inset enabled:hover:ring-border-strong'),
        className,
      )}
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

// structural-tier.md §11 "hover — the boundary thickens from `border.hairline` to `border.ring` in
// its own ink, drawn inward so nothing moves; the fill does not change" (§16.2, decided
// 2026-09-28 — corrected from the fill-deepening answer this comment used to quote, which measured
// zero surviving pixels, T675's package-wide sweep). `tests/visual/stories.spec.ts` drives the real
// `:hover` from Playwright once this story has settled (see that file's own `VisualForceState`
// comment) — a `play()` here could only dispatch a synthetic event, which the pseudo-class ignores.
// Clipped to the control: a hairline ring around one input is far under 1% of the story's frame.
const CONTROL_CLIP = { parts: [{ role: 'textbox' as const }], pad: '2' } as const

export const Hover: Story = {
  args: { label: 'Display name' },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
  parameters: {
    visualForceState: { state: 'hover', role: 'textbox' },
    visualCaptureClip: CONTROL_CLIP,
  },
}

// §11 "focus-visible — `outline-ring` at `outline-offset-ring` in `focus-ring` around the control,
// never around the whole field." T675's package-wide sweep found this story's own surviving signal
// at or under 1% of an unclipped frame in at least one unit — the same `CONTROL_CLIP` `Hover` above
// takes.
export const FocusVisible: Story = {
  args: { label: 'Display name' },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'textbox' },
    visualCaptureClip: CONTROL_CLIP,
  },
}

// §11 "active — the control's own text-entry state; no separate paint. A press on a text input is
// indistinguishable from focusing it, and pretending otherwise would be inventing a state."
export const ActiveNotApplicable: Story = {
  render: () => (
    <div className="flex max-w-xs flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A press on a text input is indistinguishable from focusing it — there is no separate active
        paint to show; see the `focus-visible` story above.
      </p>
      <Field label="Display name">
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
}

// §11 "empty — an empty value is not an error. A required field that has never been touched shows
// its default paint; it errors on blur or on submit, never on first render."
export const EmptyValueIsNotAnError: Story = {
  render: () => (
    <div className="flex max-w-xs flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        An empty value is not an error — a required field that has never been touched shows its
        default paint, identical to `Default` above, and errors only on blur or submit.
      </p>
      <Field label="Display name">
        <DemoInput defaultValue="" placeholder="e.g. TheViper" />
      </Field>
    </div>
  ),
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
