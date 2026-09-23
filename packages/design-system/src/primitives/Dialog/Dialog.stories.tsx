import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { Callout } from '../Callout'
import { Dialog } from './index'

const meta: Meta<typeof Dialog> = {
  id: 'primitives-dialog',
  title: 'Primitives/Forms/Dialog',
  component: Dialog,
  parameters: {
    docs: {
      description: {
        component: `Forces a decision on a single consequential action before it happens, blocking the rest of the page until it is made.`,
      },
    },
  },
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
// very first paint. A story verbatim identical to `Default` documents nothing (FR-037), so this
// one is forced onto `primaryAction` instead — a real control the mount effect never focuses on
// its own — via `tests/visual/stories.spec.ts`'s `visualForceState` (see that file's own comment):
// the same real Tab a keyboard user takes next from the heading (`KeyboardFocusOrderAndTrap`
// below asserts that transition functionally; this is its still-image counterpart).
// visual-equivalence: primitives-dialog--keyboard-focus-order-and-trap: forces `:focus-visible`
// synthetically onto `primaryAction` ("Turn it off"); `KeyboardFocusOrderAndTrap`'s own real
// Tab-driven sequence below ends on that same button focused via a genuine keyboard Tab — the same
// resting frame, per this comment's own point above ("this is its still-image counterpart").
export const FocusVisible: Story = {
  tags: ['visual-full-page'],
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button', name: 'Turn it off' },
  },
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

// README's gap register row 8 (H5), Cause A, closed by T600: `primaryAction.variant ?? 'destructive'`
// (`index.tsx`) is dynamic, so `state-coverage.mjs`'s own static pass cannot key this call site on
// a literal row at all — it resolves it only per story, against that story's own args (row 8's own
// Method section). No story here ever forced hover or press on `primaryAction`'s own button, so
// neither this component's real `destructive|lg` call site (this file never sets `variant` on
// `primaryAction`, so it renders the same default `destructive` this row's own args below leave
// unset) nor `AccountErasurePanel`'s own direct `destructive|lg` instance (`index.tsx:218`, no
// force-state of its own either) had a hover or press frame anywhere in the tree — F14's own
// finding. Forced here, on the same button `FocusVisible` above already targets, for the same
// reason that story does: `Default`'s own resting frame already shows this button unforced, so a
// second copy without a state change would document nothing (FR-037).
//
// `Dialog` is `position: fixed` over a full-viewport overlay (the `visual-full-page` comment at the
// top of this file), so the hover/active fill on `primaryAction` is a small mark against a mostly
// unchanged frame — well under the 1% floor at 1280 (README's contrast-signal register, row 3;
// row 8's own Method section). Clipped to the button itself, the same way `PrivacyNotice`'s
// `FIRST_LINK_CLIP`, `AccountErasurePanel`'s `checkboxClip` and `Table`'s `ROW_LINK_CLIP` clip their
// own forced-state stories — `visualCaptureClip` takes precedence over `visual-full-page` (T591).
// The clip only shrinks the frame the ratio is taken against; it does not create surviving pixels
// where the comparator (Playwright's `toHaveScreenshot`, pixelmatch at its default 0.2 threshold)
// already counts none. `active`'s border-strength delta clears that threshold before any crop, so
// the clip genuinely lifts it over the 1% floor. `hover`'s own delta is fill-only colour and clears
// nothing at that threshold at any crop — a clip cannot raise a numerator that is already zero. The
// hover half is therefore undefended regardless of this clip (T675, README's Verification-coverage
// gap register).
const PRIMARY_ACTION_CLIP = { parts: [{ role: 'button' as const, name: 'Turn it off' }], pad: '2' }

export const Hover: Story = {
  tags: ['visual-full-page'],
  parameters: {
    visualForceState: { state: 'hover', role: 'button', name: 'Turn it off' },
    visualCaptureClip: PRIMARY_ACTION_CLIP,
  },
  args: {
    heading: 'Turn off replay archival?',
    children:
      'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers.',
    primaryAction: { label: 'Turn it off' },
    secondaryAction: { label: 'Keep it on' },
  },
}

export const Active: Story = {
  tags: ['visual-full-page'],
  parameters: {
    visualForceState: { state: 'active', role: 'button', name: 'Turn it off' },
    visualCaptureClip: PRIMARY_ACTION_CLIP,
  },
  args: {
    heading: 'Turn off replay archival?',
    children:
      'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers.',
    primaryAction: { label: 'Turn it off' },
    secondaryAction: { label: 'Keep it on' },
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
