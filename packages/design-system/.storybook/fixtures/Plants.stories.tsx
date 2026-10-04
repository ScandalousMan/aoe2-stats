import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../../src/primitives/Button'
import type { ButtonVariant } from '../../src/primitives/Button'
import { Callout } from '../../src/primitives/Callout'
import { Field } from '../../src/primitives/Field'
import { Link } from '../../src/primitives/Link'
import { Menu } from '../../src/primitives/Menu'
import type { MenuProps } from '../../src/primitives/Menu'

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

// ---- args a `render:` never passes (T689) --------------------------------------------------------

// `args: { disabled: true }` on a story whose `render:` ignores its args: the mounted `Button` is not
// disabled, and nothing in the DOM is.
export const ArgsDisabledIgnored: Story = {
  args: { disabled: true },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: () => (
    <Button variant="destructive" size="md">
      Go
    </Button>
  ),
}

// Contrast: the same args, spread into the `Button`. The element it places is disabled in the DOM.
export const ArgsDisabledSpread: Story = {
  args: { disabled: true },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: (args) => <Button {...(args as { disabled?: boolean })}>Go</Button>,
}

// `args: { href: '/x' }` on a story whose `render:` ignores it: a `<button>` renders, so a force on
// role `link` finds nothing.
export const ArgsHrefIgnored: Story = {
  args: { href: '/x' },
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
  render: () => <Button>Go</Button>,
}

// `href` and `disabled` together: what renders is an `<a>`, which is never `:disabled`, so the record
// of what the browser reports disabled is empty — the reason it is read from the DOM, not from props.
export const HrefAndDisabled: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
  render: () => <Button {...({ href: '/x', disabled: true } as { href: string })}>Go</Button>,
}

// `Field` clones its control and forwards `disabled` to it: the control carries the stamp of that
// call in `Field`'s own file, and is disabled in the DOM.
export const DisabledControlInField: Story = {
  parameters: { visualForceState: { state: 'focus-visible', role: 'textbox', name: 'Name' } },
  render: () => (
    <Field label="Name">
      <input type="text" disabled />
    </Field>
  ),
}

// ---- which element a force names, and who placed it (T688) ---------------------------------------

// A raw `<a>` beside a `<Link>`, forced by role alone: two elements match.
export const RawAnchorBesideLink: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
  render: () => (
    <div>
      <a href="#raw">Raw</a>
      <Link href="#linked">Linked</Link>
    </div>
  ),
}

// The same page, forced by a `name` that picks the raw `<a>`: one match, written by the story, placed
// by no instance. The `Link` beside it, with no variant passed, is recorded at its default.
export const RawAnchorPickedByName: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'link', name: 'Raw' } },
  render: () => (
    <div>
      <a href="#raw">Raw</a>
      <Link href="#linked">Linked</Link>
    </div>
  ),
}

// A `name` that selects one of two `Button`s of different variants: one match, placed by exactly the
// instance it names.
export const NameSelectsOneOfTwo: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Cancel' } },
  render: () => (
    <div>
      <Button variant="primary">Save</Button>
      <Button variant="ghost" size="lg">
        Cancel
      </Button>
    </div>
  ),
}

// An `nth` past the last instance: nothing to select.
export const NthPastTheLast: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', nth: 2 } },
  render: () => (
    <div>
      <Button variant="primary">Save</Button>
      <Button variant="ghost" size="lg">
        Cancel
      </Button>
    </div>
  ),
}

// ---- a tag that never renders, and an axis the story never passes (T690) -------------------------

// A `Menu` behind a literal `false`: it never mounts, so the forced item is the raw one beside it and
// the story mounts no `Menu` at all.
export const GuardedMenuBesideRaw: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt' } },
  render: () => (
    <div>
      {false && <Menu variant="selection" triggerLabel="Profile" items={[]} />}
      <div role="menuitemradio" aria-checked="false" tabIndex={0}>
        aoe2alt
      </div>
    </div>
  ),
}

const MENU_ARGS = { triggerLabel: 'Profile', items: [{ id: 'one', label: 'One' }] }

// `<Menu {...args} />` with no `variant` among the args: the `Menu` renders with none, so the record
// has no variant to name (`Menu`'s `variant` has no default).
export const MenuWithoutVariant: Story = {
  args: MENU_ARGS,
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Profile' } },
  render: (args) => <Menu {...(args as MenuProps)} />,
}

// Contrast: the same spread with `variant="selection"` written after it.
export const MenuSpreadWithVariant: Story = {
  args: MENU_ARGS,
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Profile' } },
  render: (args) => <Menu {...(args as MenuProps)} variant="selection" />,
}

// ---- a guard that reads a spread (T691) ----------------------------------------------------------

const LINK_PROPS = { href: '/x' }

// `href` arrives through a spread constant: `Button` renders an `<a>`, so a force on role `button`
// finds nothing.
export const ButtonHrefViaSpreadConstant: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
  render: () => <Button {...LINK_PROPS}>Go</Button>,
}

// ---- a heading a primitive writes through a tag variable (T693, third remediation) ---------------

// `Callout` writes its heading as `const Heading = `h${level}`` then `<Heading>`: an intrinsic element
// behind a capitalised local, which the source stamp must still stamp. Forced by role, the heading is
// found once and carries `Callout`'s stamp; `Callout` is not a tracked primitive, so nothing placed it.
export const ForcedCalloutHeading: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'heading' } },
  render: () => <Callout tone="info" heading="Saved" />,
}

// The same heading, found as what holds focus after `play()` — the case the committed manifest got
// wrong while dynamic tags went unstamped (`focus: { stamp: null }` for a focused `Callout` heading).
export const PlayFocusCalloutHeading: Story = {
  play: ({ canvasElement }) => {
    canvasElement.querySelector<HTMLElement>('h2')?.focus()
  },
  render: () => <Callout tone="success" heading="Done" />,
}

// ---- a story's own element, beside and inside a primitive (T687, T689) ---------------------------

// A `<span role="slider">` the story writes as a `Button`'s child, forced by role: one match, and the
// element is the story's — no stamp, and no instance placed it, though a `Button` is all around it.
export const SliderInsideButton: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'slider' } },
  render: () => (
    <Button variant="primary" size="md">
      <span role="slider" aria-valuenow={1} aria-valuemin={0} aria-valuemax={2} tabIndex={0}>
        Level
      </span>
    </Button>
  ),
}

// A raw `<button>` beside a `<Button>`, picked by `name`: one match, written by the story, placed by
// no instance — the contrast to `TwoMatches`, where the same two elements are forced by role alone.
export const RawButtonPickedByName: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Raw' } },
  render: () => (
    <div>
      <button type="button">Raw</button>
      <Button variant="primary" size="lg">
        Composed
      </Button>
    </div>
  ),
}
