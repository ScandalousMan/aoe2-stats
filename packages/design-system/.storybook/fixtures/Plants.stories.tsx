import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../../src/primitives/Button'
import type { ButtonVariant } from '../../src/primitives/Button'
import { Callout } from '../../src/primitives/Callout'
import { Field } from '../../src/primitives/Field'
import { Menu } from '../../src/primitives/Menu'

// The plants of T693 (feature 005, `specs/005-design-system-foundations/tasks.md`): one story per
// shape the static reading of `scripts/checks/state-coverage.mjs` guessed wrong in T687–T692, built
// into Storybook so a real browser says what it does with each. `tests/visual/state-coverage-
// runtime.spec.ts` asserts the answer per plant; the committed manifest
// (`packages/design-system/specs/state-coverage-runtime.json`) records it.
//
// Tagged `state-coverage-fixture`, `!dev` and `!autodocs`: no sidebar entry, no docs page, and every
// reader of the built index that means "the stories this package publishes" skips the tag by name
// (`scripts/visual/story-index.mjs`) — no capture unit, no accessibility scan, no baseline. This file
// is not under `src/` on purpose, so the checks that walk `src/` never reach it. Plain markup, no
// styling: a plant is about which element a force selects and who placed it, not how it looks.
const meta: Meta = {
  id: 'state-coverage-fixture-plants',
  title: 'State coverage fixtures/Plants',
  tags: ['state-coverage-fixture', '!dev', '!autodocs'],
}

export default meta
type Story = StoryObj

// No match: a force names a role the story never renders. An empty `Menu` does not open, so no
// `menuitemradio` exists to hover (T691's empty-menu case; also T689's role the render never passes).
export const NoMatch: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'menuitemradio' } },
  render: () => <Menu variant="selection" triggerLabel="Profile" items={[]} />,
}

// Two matches: a raw `<button>` beside a real `<Button>`, forced by role alone (T687). Playwright's
// strict mode refuses it, so neither element can be captured.
export const TwoMatches: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: () => (
    <div>
      <button type="button">Raw</button>
      <Button variant="primary" size="lg">
        Composed
      </Button>
    </div>
  ),
}

// A stamp outside the primitive: the forced element is stamped, but by another component's file.
// A `Callout` rendered inside a `Button` is placed by `Callout`'s own source, so the `Button`
// instance around it did not place it (T692's children case).
export const StampOutsideThePrimitive: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'status' } },
  render: () => (
    <Button variant="primary" size="md">
      <Callout tone="info" heading="Note" />
    </Button>
  ),
}

// No placing instance: the forced element is a raw one a story wrote, beside a closed `Menu` that
// renders no element of that role (T688). It carries no stamp, and no instance placed it.
export const NoPlacingInstance: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'menuitemradio' } },
  render: () => (
    <div>
      <Menu variant="selection" triggerLabel="Profile" items={[]} />
      <div role="menuitemradio" aria-checked="false" tabIndex={0}>
        aoe2alt
      </div>
    </div>
  ),
}

// The axis the runtime renders: a later spread wins over an earlier literal attribute in JSX (T690),
// so this `Button` renders `destructive`, not the `secondary` written first.
export const SpreadWinsOverLiteral: Story = {
  args: { variant: 'destructive' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: (args) => (
    <Button variant="secondary" {...(args as { variant?: ButtonVariant })}>
      Go
    </Button>
  ),
}

// The axis the runtime renders, by default: a bare `<Button>` names neither axis and renders
// `secondary|md` (T689's extension corrected this exact default once).
export const BareButton: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: () => <Button>Go</Button>,
}

// A cloned control: `Field` places its child by `cloneElement`, so the control carries the stamp of
// that call in `Field`'s own file and is attributed to the `Field` instance (T692's contrast case).
export const ClonedControl: Story = {
  parameters: { visualForceState: { state: 'focus-visible', role: 'textbox', name: 'Name' } },
  render: () => (
    <Field label="Name">
      <input type="text" />
    </Field>
  ),
}

// An `aria-hidden` ancestor: Playwright's `getByRole` cannot find a control inside one, so a force
// naming it matches nothing (T692's first case).
export const HiddenAncestor: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: () => (
    <div aria-hidden="true">
      <Button variant="primary" size="lg">
        Go
      </Button>
    </div>
  ),
}

// A `play()`-focus story: what holds focus once `play()` has run is recorded, with its stamp and
// the instance that placed it.
export const PlayFocus: Story = {
  play: ({ canvasElement }) => {
    canvasElement.querySelector('button')?.focus()
  },
  render: () => (
    <Button variant="ghost" size="md">
      Go
    </Button>
  ),
}
