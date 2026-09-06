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
