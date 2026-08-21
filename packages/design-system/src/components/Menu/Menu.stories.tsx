import type { Meta, StoryObj } from '@storybook/react-vite'
import { Menu } from './index'

const meta: Meta<typeof Menu> = {
  title: 'Primitives/Menu',
  component: Menu,
}

export default meta
type Story = StoryObj<typeof Menu>

export const ProfileSwitcher: Story = {
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
  args: {
    variant: 'selection',
    triggerLabel: 'aoe2guy — profile ▾',
    items: [{ id: 'p1', label: 'aoe2guy', checked: true, badge: <span>Primary</span> }],
    footerItem: { id: 'link', label: 'Link another Steam account' },
  },
}

export const ActionsWithDisabledItem: Story = {
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
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [{ id: 'unlink', label: 'Unlink this profile' }],
    errorItemId: 'unlink',
    errorMessage: 'We could not unlink that profile',
  },
}

export const Empty: Story = {
  args: {
    variant: 'actions',
    triggerLabel: 'Manage',
    items: [],
  },
}
