import type { Meta, StoryObj } from '@storybook/react-vite'
import { CaptureStateBadge } from './index'

const meta: Meta<typeof CaptureStateBadge> = {
  title: 'Composite/CaptureStateBadge',
  component: CaptureStateBadge,
}

export default meta
type Story = StoryObj<typeof CaptureStateBadge>

// Deadlines are computed relative to render time, not a fixed date, so the countdown text stays
// the same ("6 days left", "18 hours left", ...) no matter which day this story is captured —
// see countdown.ts's own note on why the pure function takes `now` rather than reading the clock.
const HOUR_MS = 60 * 60_000
const DAY_MS = 24 * HOUR_MS

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

// The user-facing label for `stored` — never "Safe" (capture-state-badge.md §3).
export const Archived: Story = {
  args: { captureStatus: 'stored' },
}

export const StillCatchableDays: Story = {
  args: { captureStatus: 'pending', captureDeadlineAt: inFromNow(6 * DAY_MS) },
}

export const StillCatchableHours: Story = {
  args: { captureStatus: 'pending', captureDeadlineAt: inFromNow(18 * HOUR_MS) },
}

export const StillCatchableMinutes: Story = {
  args: { captureStatus: 'downloading', captureDeadlineAt: inFromNow(42 * 60_000) },
}

export const StillCatchableWindowClosing: Story = {
  name: 'Still catchable — window closing (deadline already passed)',
  args: { captureStatus: 'pending', captureDeadlineAt: inFromNow(-5 * 60_000) },
}

export const StillCatchableNoDeadline: Story = {
  name: 'Still catchable — no deadline yet (should not happen, never trusted blindly)',
  args: { captureStatus: 'pending', captureDeadlineAt: null },
}

export const LostUnavailable: Story = {
  name: 'Lost — unavailable (never recorded server-side)',
  args: { captureStatus: 'unavailable' },
}

export const LostExpired: Story = {
  name: 'Lost — expired (ours to own, upload likely to help)',
  args: { captureStatus: 'expired' },
}

export const LostFailed: Story = {
  name: 'Lost — failed (repeated capture attempts failed)',
  args: { captureStatus: 'failed' },
}

export const NeedsReview: Story = {
  args: { captureStatus: 'quarantined' },
}

export const DetailContext: Story = {
  name: 'Detail context — stacked, full-sentence SecondaryLine',
  args: { captureStatus: 'expired', context: 'detail' },
}

export const DetailContextCountdown: Story = {
  name: 'Detail context — countdown as a full sentence',
  args: { captureStatus: 'pending', captureDeadlineAt: inFromNow(6 * DAY_MS), context: 'detail' },
}

// §6 "loading": a Skeleton matching the pill's own footprint, never a placeholder tone.
export const Loading: Story = {
  args: { loading: true },
}

// §6 "empty": no `ReplayCapture` row exists yet — renders nothing. Rendered inside a labelled
// wrapper so the empty result is visibly confirmable rather than an indistinguishable blank canvas.
export const Empty: Story = {
  render: () => (
    <div className="rounded-sm border border-dashed border-border p-4 font-sans text-xs text-text-secondary">
      Nothing renders below this line —{' '}
      <span className="inline-block align-middle">
        <CaptureStateBadge captureStatus={null} />
      </span>
    </div>
  ),
}

// §6 "error": an unrecognised status still reads as a word, in a neutral badge, no SecondaryLine.
export const UnrecognisedStatus: Story = {
  args: { captureStatus: 'a_future_status_this_build_does_not_know' },
}

// Acceptance: all four tones distinct from each other, in the same screenshot, and — converted to
// greyscale — still distinguishable by label text alone.
export const AllFourStates: Story = {
  render: () => (
    <ul className="flex flex-col gap-4">
      <li>
        <CaptureStateBadge captureStatus="stored" />
      </li>
      <li>
        <CaptureStateBadge captureStatus="pending" captureDeadlineAt={inFromNow(6 * DAY_MS)} />
      </li>
      <li>
        <CaptureStateBadge captureStatus="unavailable" />
      </li>
      <li>
        <CaptureStateBadge captureStatus="expired" />
      </li>
      <li>
        <CaptureStateBadge captureStatus="failed" />
      </li>
      <li>
        <CaptureStateBadge captureStatus="quarantined" />
      </li>
    </ul>
  ),
}
