import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'
import { Menu } from './index'

const meta: Meta<typeof Menu> = {
  id: 'primitives-menu',
  title: 'Primitives/Forms/Menu',
  component: Menu,
  parameters: {
    docs: {
      description: {
        component: `Offers a short, known set of choices from a trigger, without leaving the page.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof Menu>

// The surface only exists once the trigger is clicked (index.tsx keeps `open` as internal state,
// on purpose — see shared-primitives.md §Menu's "empty" state, which depends on the trigger being
// unopenable). Every story below except `Empty` names an *open* state, so its baseline has to show
// one: the play function opens it the same way a person would, rather than adding an `open` prop
// to the component whose only consumer would be the visual test.
async function openMenu({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.click(canvas.getByRole('button'))
  await canvas.findByRole('menu')
}

// `visual-full-page` (scripts/visual/run.mjs): the open popover is absolutely positioned against
// the trigger's own box, which does not grow to contain it, so a screenshot clipped to the story
// root never reaches it — the visual run has to capture the whole page instead.
export const ProfileSwitcher: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

export const SingleProfile: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [{ id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> }],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// FR-044: `isSheet = !useBreakpoint('md')` (index.tsx's own doc comment) — a full-width bottom
// sheet below `md`, an anchored popover from it, one DOM tree restructured at the breakpoint.
// Pinned toward the narrow shape with the declared `reviewWidthNarrow` viewport via
// `globals.viewport` (see `MatchRow.stories.tsx`'s identical rationale for why a declared option
// rather than a Storybook device preset) — `ProfileSwitcher` above already reads at the wide,
// popover shape.
// visual-equivalence: primitives-menu--profile-switcher: the reviewWidthNarrow viewport pin is
// overridden by the visual suite's own 375/768/1280 capture axis (T504), and the args are identical
// to ProfileSwitcher's, so all six baselines match.
export const SheetBelowMd: Story = {
  name: 'Bottom sheet below md, an anchored popover from it',
  tags: ['visual-full-page'],
  globals: { viewport: { value: 'reviewWidthNarrow' } },
  play: openMenu,
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

export const ActionsWithDisabledItem: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [
      {
        id: 'make-primary',
        label: 'Make primary',
        disabled: true,
        disabledReason: 'Already primary',
      },
      { id: 'unlink', label: 'Unlink this profile' },
    ],
  },
}

export const LoadingItem: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, loading: true },
      {
        id: 'p2',
        label: 'aoe2alt',
        checked: false,
        disabled: true,
        disabledReason: 'A change is in progress',
      },
    ],
  },
}

export const ItemError: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [{ id: 'unlink', label: 'Unlink this profile' }],
    errorItemId: 'unlink',
    errorMessage: 'We could not unlink that profile',
  },
}

// No `play` here: an empty menu never opens (shared-primitives.md §Menu, "empty"), so its
// baseline is meant to be the disabled trigger, not a surface.
export const Empty: Story = {
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [],
  },
}

// §Menu "hover — item fill `surface-sunken`." `play()` here only opens the menu (a real state
// change, since the component's own `onClick` handler responds to a synthetic click just as it
// would a real one) — `tests/visual/stories.spec.ts` drives the real `:hover` on the item itself
// from Playwright, once the menu has opened and the story has settled, because a synthetic
// `userEvent.hover()` would dispatch an event every listener sees but the `:hover` pseudo-class
// itself ignores (see that file's own `VisualForceState` comment).
export const Hover: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  parameters: {
    visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt' },
  },
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// §Menu "focus-visible — the focused item shows the standard focus ring inset within its bounds.
// Focus follows the roving item, never both trigger and item."
//
// T572 scenario 9 remediation (residual 2): opening focuses the *checked* item by default
// (`index.tsx`'s own `checkedIndex` effect), so this story used to land on the exact same row
// `Selection`/`ProfileSwitcher` already show checked — a reader comparing the three stories saw
// focus and selection as one and the same signal, even after the checkmark glyph fix made checked
// and unchecked rows distinguishable *within* a single image. Forced onto `aoe2alt`, the
// *unchecked* row, instead, so this story's own still image shows a focus ring on a row that
// carries no checkmark glyph — focus and selection now read as two independent facts here too, not
// only within `Selection`'s own frame. `play()` here only opens the menu (the same `openMenu`
// every other story on this page uses); `tests/visual/stories.spec.ts` drives the real
// `:focus-visible` from Playwright afterward (see that file's own `VisualForceState` comment) —
// a synthetic keyboard event here could open the menu (a real state change other listeners
// receive) but not itself the pseudo-class.
export const FocusVisible: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2alt' },
  },
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// FR-045: keyboard interaction beyond opening — `onItemKeyDown` in `index.tsx` moves the roving
// item with Arrow keys and jumps to either end with Home/End. Asserted, not only driven: the
// roving `tabIndex` swap between items is a state a screenshot alone would not prove.
//
// T572 scenario 9 remediation (defect 2): this story used to end with `{Escape}` and an assertion
// that focus returns to the trigger, so its resting frame — the frame the visual baseline actually
// captures — was a closed trigger with a focus ring, documenting nothing about keyboard
// navigation. The Escape/return-focus coverage was not deleted, only moved: it is exactly what
// `EscapeReturnsFocusToTrigger` below exists to demonstrate, where a closed, refocused trigger *is*
// the point rather than an accident of the play function's own ending. This story instead now ends
// on `{End}`, so its resting frame shows the footer row focused — a state neither `FocusVisible`
// (first item) nor `Active` (a mouse press on the second item) already shows, so it is worth
// capturing on its own.
export const KeyboardNavigation: Story = {
  tags: ['visual-full-page'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    const first = await canvas.findByRole('menuitemradio', { name: /aoe2guy/ })
    await expect(first).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}')
    const second = canvas.getByRole('menuitemradio', { name: /aoe2alt/ })
    await expect(second).toHaveFocus()
    await userEvent.keyboard('{Home}')
    await expect(first).toHaveFocus()
    await userEvent.keyboard('{End}')
    const footer = canvas.getByRole('menuitem', { name: 'Link another Steam account' })
    await expect(footer).toHaveFocus()
  },
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// The other half of the split above: FR-045's "Escape closes the surface and returns focus to the
// trigger" as its own story, so the closed, refocused trigger this play function ends on is the
// documented state, not a leftover. No `visual-full-page` tag — like `Empty` and `ClosedTrigger`,
// nothing here escapes the trigger's own layout box, so the default clipped capture already
// reaches it.
export const EscapeReturnsFocusToTrigger: Story = {
  name: 'Escape closes the surface and returns focus to the trigger',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    await canvas.findByRole('menu')
    await userEvent.keyboard('{Escape}')
    expect(canvas.queryByRole('menu')).not.toBeInTheDocument()
    await expect(trigger).toHaveFocus()
  },
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// FR-034/FR-037 (T569 residual 2): a story literally named for the *selection* vocabulary entry.
// `ProfileSwitcher` above already shows the same shape — `checked: true` plus a trailing badge —
// but is named for its consumer's scenario, not the state, so a reader browsing for "selection" or
// `visual-reviewer` mapping a capture to the vocabulary has nothing to find. Added rather than
// renaming `ProfileSwitcher`: renaming an export changes its story id and orphans the checked-in
// baseline.
// visual-equivalence: primitives-menu--profile-switcher: args are identical to ProfileSwitcher's —
// this story exists so the selection vocabulary entry has something to find, not to depict a
// distinct rendering (see this comment's own point above).
export const Selection: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

// FR-034/FR-037 (T569 residual 2): a story literally named for the *expansion* vocabulary entry —
// the trigger's `aria-expanded` true, the panel drawn beside it. Every other `visual-full-page`
// story above already opens the panel via `play`, but none is named for the state itself. Paired
// with `ClosedTrigger` below, the resting half; a still image of one without the other has nothing
// to be distinguishable from (README's governing requirement, T569). `actions` rather than
// `selection`: this story is about the disclosure, not the checked item, which `Selection` above
// already owns.
export const Expansion: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [
      { id: 'make-primary', label: 'Make primary' },
      { id: 'unlink', label: 'Unlink this profile' },
    ],
  },
}

// The resting half of the expansion pair (T569 residual 2): a closed, *non-empty* trigger, so the
// open panel above has something to be distinguishable from in a still image. `Empty` below is the
// only existing closed-trigger story, and its trigger is `aria-disabled` — it cannot stand in for
// "closed" generally, only for the empty state. No `play`: the point is the unopened, operable
// trigger.
export const ClosedTrigger: Story = {
  name: 'Closed trigger — the resting half of expansion',
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [
      { id: 'make-primary', label: 'Make primary' },
      { id: 'unlink', label: 'Unlink this profile' },
    ],
  },
}

// §Menu "active — item fill `surface-sunken` with boundary `border-strong` on the inline-start
// edge." Held down rather than released so the capture shows the pressed frame. `play()` here
// only opens the menu; the real `:active` state is driven from Playwright afterward (see `Hover`
// above's comment).
export const Active: Story = {
  tags: ['visual-full-page'],
  play: openMenu,
  parameters: {
    visualForceState: { state: 'active', role: 'menuitemradio', name: 'aoe2alt' },
  },
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [
      { id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> },
      { id: 'p2', label: 'aoe2alt', checked: false },
    ],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}
