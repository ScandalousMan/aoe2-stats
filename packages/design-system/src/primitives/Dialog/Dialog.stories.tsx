import type { Meta, StoryObj } from '@storybook/react-vite'
import { Dialog } from './index'

const meta: Meta<typeof Dialog> = {
  title: 'Primitives/Dialog',
  component: Dialog,
}

export default meta
type Story = StoryObj<typeof Dialog>

// `visual-full-page` (scripts/visual/run.mjs): the dialog is `position: fixed`, which paints
// relative to the viewport rather than the story root — a screenshot clipped to that root would
// capture neither the dialog nor the overlay behind it.
export const Default: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Turn off replay archival?',
    children:
      'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers.',
    primaryAction: { label: 'Turn it off' },
    secondaryAction: { label: 'Keep it on' },
  },
}

export const WithBodyAndError: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Unlink aoe2guy?',
    children: 'You have 12 replays archived from this profile. They stay archived after unlinking.',
    primaryAction: { label: 'Unlink this profile' },
    secondaryAction: { label: 'Keep it linked' },
  },
}

export const PrimaryPending: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Unlink aoe2guy?',
    children: 'You have 12 replays archived from this profile. They stay archived after unlinking.',
    primaryAction: { label: 'Unlink this profile', loading: true, loadingLabel: 'Unlinking…' },
    secondaryAction: { label: 'Keep it linked', disabled: true },
  },
}
