import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { ThirdPartyObjectionForm } from './index'

const meta: Meta<typeof ThirdPartyObjectionForm> = {
  id: 'screens-thirdpartyobjectionform',
  title: 'Screens/Account & privacy/ThirdPartyObjectionForm',
  component: ThirdPartyObjectionForm,
  parameters: {
    docs: {
      description: {
        component: `Lets a person who never signed in understand what this service holds about them and lodge an objection that a human will act on.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof ThirdPartyObjectionForm>

// `initialState` renders one fixed frame without driving a real promise (third-party-objection.md
// §3) — `onSubmit` below is never actually exercised by these stories.
const noopHandlers = {
  onSubmit: () => new Promise<void>(() => {}),
  privacyNoticeHref: '/privacy-notice',
}

export const Idle: Story = {
  name: 'default — explanation above an empty, enabled field',
  args: { ...noopHandlers, initialState: 'idle' },
}

export const Submitting: Story = {
  name: 'submitting — busy button, same width as at rest, field read-only',
  args: { ...noopHandlers, initialState: 'submitting' },
}

export const Recorded: Story = {
  name: 'recorded — success callout; nothing claims data was already changed',
  args: { ...noopHandlers, initialState: 'recorded' },
}

export const RateLimited: Story = {
  name: 'rate-limited — warning callout, try-again message, button present',
  args: { ...noopHandlers, initialState: 'rate-limited' },
}

export const Failed: Story = {
  name: 'failed — danger callout, nothing recorded, button enabled again',
  args: { ...noopHandlers, initialState: 'failed' },
}

// third-party-objection.md §5 "error — ... `FieldError` inline for a bad value" — a client-side
// validation error, distinct from the two `FormFailure` stories above, reached by submitting a
// non-numeric value the same way a real stranger would.
export const FieldError: Story = {
  name: 'field error — a non-numeric value, inline, focus moved to the field',
  args: { ...noopHandlers, initialState: 'idle' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByRole('textbox'), 'not-a-number')
    await userEvent.click(canvas.getByRole('button', { name: 'Record my objection' }))
  },
}

// §5 "disabled — the submit button is never disabled. Validation happens on submit, not by
// greying the button."
// §5 "hover — the privacy-notice link... and the submit button (per `Button`)." Forced from
// Playwright in `tests/visual/stories.spec.ts` (see that file's own `VisualForceState` comment) —
// a `play()` could only dispatch a synthetic event, which the CSS pseudo-class ignores.
// T591: this group clips to the privacy-notice link — the hover/press underline-thickness signal
// is a small mark on the whole form's frame, invisible to the duplicate check at that scale
// (story-baseline-duplicates-debt.json).
const LINK_CLIP = { parts: [{ role: 'link' }], pad: '2' } as const

export const Hover: Story = {
  args: { ...noopHandlers, initialState: 'idle' },
  parameters: { visualForceState: { state: 'hover', role: 'link' }, visualCaptureClip: LINK_CLIP },
}

// §5 "focus-visible — the standard ring... on the input, the submit button and the
// privacy-notice link."
export const FocusVisible: Story = {
  args: { ...noopHandlers, initialState: 'idle' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link' },
    visualCaptureClip: LINK_CLIP,
  },
}

// §5 "active — the link renders `accent-active` while pressed; the button per `Button`."
export const Active: Story = {
  args: { ...noopHandlers, initialState: 'idle' },
  parameters: { visualForceState: { state: 'active', role: 'link' }, visualCaptureClip: LINK_CLIP },
}

export const DisabledNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The submit button is never disabled — validation happens on submit, not by greying the
        button, so a stranger meeting this form once is never faced with a dead control.
      </p>
      <ThirdPartyObjectionForm {...args} />
    </div>
  ),
  args: { ...noopHandlers, initialState: 'idle' },
}
