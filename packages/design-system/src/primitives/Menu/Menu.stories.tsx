import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { Menu } from './index'

const meta: Meta<typeof Menu> = {
  title: 'Primitives/Menu',
  component: Menu,
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

// §Menu "hover — item fill `surface-sunken`."
export const Hover: Story = {
  tags: ['visual-full-page'],
  play: async ({ canvasElement }) => {
    await openMenu({ canvasElement })
    const canvas = within(canvasElement)
    await userEvent.hover(canvas.getByRole('menuitemradio', { name: /aoe2alt/ }))
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
// Focus follows the roving item, never both trigger and item." Opened by keyboard (Enter on the
// trigger) rather than by click, which is what actually reaches `:focus-visible` in Chromium's own
// heuristic — the same reach `tests/visual/focus-ring.spec.ts` uses for this component.
export const FocusVisible: Story = {
  tags: ['visual-full-page'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    await canvas.findByRole('menu')
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

// §Menu "active — item fill `surface-sunken` with boundary `border-strong` on the inline-start
// edge." Held down rather than released so the capture shows the pressed frame.
export const Active: Story = {
  tags: ['visual-full-page'],
  play: async ({ canvasElement }) => {
    await openMenu({ canvasElement })
    const canvas = within(canvasElement)
    const item = canvas.getByRole('menuitemradio', { name: /aoe2alt/ })
    await userEvent.pointer({ keys: '[MouseLeft>]', target: item })
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
