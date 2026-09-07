import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { Callout } from '../Callout'
import { Dialog } from './index'

const meta: Meta<typeof Dialog> = {
  id: 'primitives-dialog',
  title: 'Primitives/Forms/Dialog',
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

// §Dialog's `focus-visible` bullet states focus moves to the heading (`tabIndex={-1}`) on mount —
// the same rendering `Default` above already shows, since that focus happens synchronously on the
// very first paint. Named separately here too, so the state has its own entry in the sidebar,
// matching the closed vocabulary.
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

// FR-045/FR-049: the focus order inside the trap. Focus lands on the heading on mount (`Dialog.
// test.tsx` covers that transition already); this shows the sequence a keyboard user drives next —
// Tab reaches `primaryAction` (rendered first, `index.tsx`'s own doc comment), then
// `secondaryAction`, and Tab from the last one wraps back to the first rather than escaping the
// dialog — the one trap FR-049 permits ("no trap outside a modal surface that defines its own").
export const KeyboardFocusOrderAndTrap: Story = {
  tags: ['visual-full-page'],
  args: {
    heading: 'Turn off replay archival?',
    children:
      'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers.',
    primaryAction: { label: 'Turn it off' },
    secondaryAction: { label: 'Keep it on' },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const heading = canvas.getByRole('heading', { name: 'Turn off replay archival?' })
    // The mount effect (`headingRef.current?.focus()`) commits a tick after this play function
    // starts, the same race `CountryFlag.stories.tsx`'s own focus assertions already wait out.
    await waitFor(() => expect(heading).toHaveFocus())
    const primary = canvas.getByRole('button', { name: 'Turn it off' })
    const secondary = canvas.getByRole('button', { name: 'Keep it on' })
    await userEvent.tab()
    await expect(primary).toHaveFocus()
    await userEvent.tab()
    await expect(secondary).toHaveFocus()
    await userEvent.tab()
    await expect(primary).toHaveFocus()
  },
}

// §Dialog's "empty / hover / active / disabled — not applicable; a dialog with no actions is a
// malformed call site, and hover, active and disabled all belong to the `Button`s inside it — not
// to the dialog itself." `disabled` shares that bullet rather than owning one of its own: a dialog
// is not itself disableable, only the actions inside it are, via their own `disabled` prop (see
// `PrimaryPending` above).
export const EmptyHoverActiveDisabledNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      A dialog with no actions is a malformed call site — there is no empty rendering to show.
      Hover, active and disabled all belong to the `Button`s inside it, never to the dialog itself.
    </p>
  ),
}
