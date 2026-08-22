import { useEffect, useId, useState } from 'react'
import { cx } from '../../lib/cx'
import { Badge } from '../Badge'
import type { BadgeVariant } from '../Badge'
import { Skeleton } from '../Skeleton'
import { describeCaptureCountdown } from './countdown'
import type { CaptureStateBadgeContext } from './countdown'

// packages/design-system/specs/capture-state-badge.md

/** The seven raw `replay_captures.status` values (data-model.md). Typed as a string union with a
 * fallback so an unrecognised value from the wire still type-checks — the component's own §6
 * "error" state exists for exactly that case, rather than a type assertion papering over it. */
export type CaptureStatus =
  'pending' | 'downloading' | 'stored' | 'unavailable' | 'expired' | 'failed' | 'quarantined'

export type { CaptureStateBadgeContext }

export interface CaptureStateBadgeProps {
  /** One of the seven raw values, or any other string (§6 "error"), or `null`/`undefined` — no
   * `ReplayCapture` row exists yet for this match (§6 "empty"), which renders nothing. */
  // `string & {}` keeps literal autocomplete for the known seven while still accepting any other
  // string — §6 "error" is exactly that case, an unrecognised value that must still type-check.
  captureStatus?: CaptureStatus | (string & {}) | null
  /** ISO 8601, or `null`. Consulted only while `captureStatus` is `pending`/`downloading`. */
  captureDeadlineAt?: string | null
  /** `compact` inside `MatchRow`, `detail` inside `MatchDetailPanel` (match-history.md). */
  context?: CaptureStateBadgeContext
  /** The owning row has not received `capture_status` yet: renders a `Skeleton` matching the
   * pill's own footprint in place of the badge (§6 "loading"). Takes priority over every other
   * prop, including a `captureStatus` left over from a previous render. */
  loading?: boolean
  className?: string
}

const TONE_BY_STATUS: Partial<Record<CaptureStatus, { label: string; variant: BadgeVariant }>> = {
  stored: { label: 'Archived', variant: 'success' },
  pending: { label: 'Still catchable', variant: 'warning' },
  downloading: { label: 'Still catchable', variant: 'warning' },
  unavailable: { label: 'Lost', variant: 'danger' },
  expired: { label: 'Lost', variant: 'danger' },
  failed: { label: 'Lost', variant: 'danger' },
  quarantined: { label: 'Needs review', variant: 'info' },
}

// The three "Lost" statuses and "Needs review" carry the *reason* as SecondaryLine, because they
// send the user to different places (§3). `stored` has none: "Archived" needs no further sentence.
const REASON: Partial<Record<CaptureStatus, string>> = {
  unavailable:
    'The game never recorded this match. Your own saved games folder is probably empty too.',
  expired:
    'The replay existed, but we did not capture it in time. If you still have the file, you can upload it.',
  failed:
    'We could not capture this replay after repeated attempts. If you still have the file, you can upload it.',
  quarantined:
    'We have a copy, but it failed validation. It is kept for review — there is nothing further for you to do.',
}

const CATCHABLE = new Set<CaptureStatus>(['pending', 'downloading'])

// "Recomputed on an interval no coarser than once per minute while the component is mounted"
// (§7). Only ticks while the countdown is actually on screen, so an archived or lost row never
// re-renders on a timer it has no use for.
function useTickingNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!active) return undefined
    const id = window.setInterval(() => setNow(Date.now()), 60_000)
    return () => window.clearInterval(id)
  }, [active])

  return now
}

function secondaryLineFor(
  status: CaptureStatus,
  deadlineAt: string | null,
  now: number,
  context: CaptureStateBadgeContext,
): string | undefined {
  if (CATCHABLE.has(status)) {
    // "Never a countdown built from a missing value" (§6) — should not happen per data-model.md,
    // but a missing deadline renders the pill with no SecondaryLine rather than trusted blindly.
    return deadlineAt ? describeCaptureCountdown(deadlineAt, now, context) : undefined
  }
  return REASON[status]
}

/** The single place `replay_captures.status`'s seven raw values collapse into the four states a
 * user sees. Never called with a caller-chosen label or tone — see capture-state-badge.md §3. */
export function CaptureStateBadge({
  captureStatus,
  captureDeadlineAt = null,
  context = 'compact',
  loading = false,
  className,
}: CaptureStateBadgeProps) {
  const isCatchable = captureStatus != null && CATCHABLE.has(captureStatus as CaptureStatus)
  const now = useTickingNow(!loading && isCatchable)
  const secondaryId = useId()

  if (loading) {
    // Pill footprint: `space-5` tall, ~90px wide (§6) — `w-24` (space scale) is the closest
    // token-backed step to that approximation; there is no dedicated pill-width token.
    // `variant="block"` (not `text`): `text` ignores the caller's size and varies its own width
    // for a paragraph line, which is wrong for a single pill's fixed footprint.
    return <Skeleton variant="block" className={cx('h-5 w-24', className)} />
  }

  if (!captureStatus) return null

  const known = TONE_BY_STATUS[captureStatus as CaptureStatus]

  if (!known) {
    // Forward-compatibility guard (§6 "error"): a status this component cannot classify still
    // reads as a word, never a blank pill and never a guessed tone.
    return <Badge variant="neutral">{captureStatus}</Badge>
  }

  const secondary = secondaryLineFor(
    captureStatus as CaptureStatus,
    captureDeadlineAt,
    now,
    context,
  )

  return (
    <div
      className={cx(
        'flex',
        context === 'detail'
          ? 'flex-col items-start gap-1'
          : 'flex-col items-start gap-2 sm:flex-row sm:items-center',
        className,
      )}
    >
      <span aria-describedby={secondary ? secondaryId : undefined}>
        <Badge variant={known.variant}>{known.label}</Badge>
      </span>
      {secondary && (
        <span id={secondaryId} className="font-sans text-xs font-normal text-text-secondary">
          {secondary}
        </span>
      )}
    </div>
  )
}
