import type { Meta, StoryObj } from '@storybook/react-vite'
import { Callout } from '../Callout'
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

// shared-primitives.md §Dialog "error — the caller renders a `Callout` in the body slot; the
// dialog itself has no error state." Shown with the `Callout` actually in the body, which
// `WithBodyAndError` above does not carry despite its name.
export const Error: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Unlink aoe2guy?',
    children: (
      <Callout tone="danger" heading="We could not unlink that profile">
        Try again in a moment. If this keeps happening, contact support with reference UNLINK-409.
      </Callout>
    ),
    primaryAction: { label: 'Unlink this profile' },
    secondaryAction: { label: 'Keep it linked' },
  },
}

// §Dialog "focus-visible" is not named as its own bullet, but the accessibility section states
// focus moves to the heading (`tabIndex={-1}`) on mount — the same rendering `Default` above
// already shows, since that focus happens synchronously on the very first paint. Named separately
// so the state has its own entry in the sidebar, matching the closed vocabulary.
export const FocusVisible: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Turn off replay archival?',
    children:
      'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers.',
    primaryAction: { label: 'Turn it off' },
    secondaryAction: { label: 'Keep it on' },
  },
}

// §Dialog "empty / hover / active — not applicable; a dialog with no actions is a malformed call
// site, and hover/active belong to the `Button`s inside it, not to the dialog itself." `disabled`
// has no bullet of its own in this spec; the same reasoning applies by extension — a dialog is not
// itself disableable, only the actions inside it are, via their own `disabled` prop (see
// `PrimaryPending` above).
export const EmptyHoverActiveDisabledNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A dialog with no actions is a malformed call site — there is no empty rendering to show.
      Hover, active and disabled all belong to the `Button`s inside it, never to the dialog itself.
    </p>
  ),
}
