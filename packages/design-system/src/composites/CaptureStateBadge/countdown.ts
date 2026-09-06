// packages/design-system/specs/capture-state-badge.md §7 — the "Still catchable" countdown.
//
// A pure function so the unit/pluralisation/overdue logic is testable without mounting a
// component or faking a timer. The component (index.tsx) supplies `now` from its own ticking
// clock; Storybook stories supply a `captureDeadlineAt` computed relative to render time, so the
// rendered text ("6 days left") stays the same on every run regardless of which day it runs on.

export type CaptureStateBadgeContext = 'compact' | 'detail'

const MINUTE_MS = 60_000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

interface RemainingParts {
  amount: number
  unit: 'day' | 'hour' | 'minute'
}

// Floor, never round — "6 days left" never means less than 144 hours remain (§7).
function remainingParts(remainingMs: number): RemainingParts {
  const days = Math.floor(remainingMs / DAY_MS)
  if (days >= 1) return { amount: days, unit: 'day' }

  const hours = Math.floor(remainingMs / HOUR_MS)
  if (hours >= 1) return { amount: hours, unit: 'hour' }

  const minutes = Math.floor(remainingMs / MINUTE_MS)
  return { amount: minutes, unit: 'minute' }
}

function pluralise(amount: number, unit: string): string {
  return amount === 1 ? unit : `${unit}s`
}

/** `deadlineAt` — ISO 8601. `now` — epoch ms, supplied by the caller's own clock (never reads
 * `Date.now()` itself, so it stays a pure function). Never returns a negative countdown: once the
 * deadline has passed — an expected, brief race against the daily sweep while `capture_status`
 * still reads `pending`/`downloading` — it returns the "closing" sentence instead (§7). */
export function describeCaptureCountdown(
  deadlineAt: string,
  now: number,
  context: CaptureStateBadgeContext,
): string {
  const remainingMs = new Date(deadlineAt).getTime() - now

  if (remainingMs <= 0) {
    return context === 'compact' ? 'Capture window closing' : 'This capture is due any moment.'
  }

  const { amount, unit } = remainingParts(remainingMs)
  const label = pluralise(amount, unit)

  return context === 'compact'
    ? `${amount} ${label} left`
    : `Captures automatically within ${amount} ${label}.`
}
