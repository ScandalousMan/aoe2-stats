import { useEffect, useId, useState } from 'react'
import { cx } from '../../lib/cx'
import { Badge } from '../../primitives/Badge'
import type { BadgeVariant } from '../../primitives/Badge'
import { Skeleton } from '../../primitives/Skeleton'
import { describeCaptureCountdown } from './countdown'
import type { CaptureStateBadgeVariant } from './countdown'

// packages/design-system/specs/capture-state-badge.md

/** The eight raw `replay_captures.status` values: data-model.md's seven and `withdrawn` (T721,
 * capture-state-badge.md §1). Typed as a string union with a fallback so an unrecognised value
 * from the wire still type-checks — the component's own §6 "error" state exists for exactly that
 * case, rather than a type assertion papering over it. */
export type CaptureStatus =
  | 'pending'
  | 'downloading'
  | 'stored'
  | 'unavailable'
  | 'expired'
  | 'failed'
  | 'quarantined'
  | 'withdrawn'

export type { CaptureStateBadgeVariant }

export interface CaptureStateBadgeProps {
  /** One of the eight raw values, or any other string (§6 "error"), or `null`/`undefined` — no
   * `ReplayCapture` row exists yet for this match (§6 "empty"), which renders nothing. */
  // `string & {}` keeps literal autocomplete for the known eight while still accepting any other
  // string — §6 "error" is exactly that case, an unrecognised value that must still type-check.
  captureStatus?: CaptureStatus | (string & {}) | null
  /** ISO 8601, or `null`. Consulted only while `captureStatus` is `pending`/`downloading` and
   * `archivalObjected` is not set: with it, the deadline is never read (§7). */
  captureDeadlineAt?: string | null
  /** `GET /api/me`'s `archival_objected` (§4, T724, T729). `MatchDetailPanel` passes it for every
   * match: the detail route joins a capture row only for the caller's linked profiles, so any
   * other match has a `null` `captureStatus` and renders nothing. `MatchList` forwards it whatever
   * the `subject` (T726): a third party's rows carry a `null` status, so it reaches only the
   * caller's own. With it a `pending`/`downloading` row reads "Not archived" as `withdrawn`
   * does, with "Archival is off for your account." in `detail` and no countdown or interval; an
   * `expired`/`failed` row stays "Lost" and drops the upload sentence, as no upload is offered
   * under it. Every other status ignores it. */
  archivalObjected?: boolean
  /** `compact` inside `MatchRow`, `detail` inside `MatchDetailPanel` (match-history.md). Renamed
   * from `context` (FR-032, T557): every other component whose rendering depends on where it is
   * embedded calls this `variant`. */
  variant?: CaptureStateBadgeVariant
  /** Force the pill and `SecondaryLine` to always stack, regardless of the *window's* width.
   * `variant="compact"`'s own default (`sm:flex-row` at 640px-equivalent) reads the window, which
   * is the right approximation for a full-width `MatchRow` card but the wrong one for a caller
   * whose own box is narrower than the window — e.g. `MatchRow`'s bounded trailing table column
   * (match-history.md §8: "`SecondaryLine` beneath the pill rather than beside it, column width
   * is bounded"). Rather than have this component infer a container width it cannot observe, the
   * caller that knows its own box is bounded tells it so. No effect on `variant="detail"`, which
   * already always stacks. */
  stacked?: boolean
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
  // A fifth state, not a fourth "Lost" (§3, T721): the write that sets it read ownership as it
  // ran. `neutral`, never `danger`. The raw word "withdrawn" is never a label — a known status
  // must not reach the §6 fallback.
  withdrawn: { label: 'Not archived', variant: 'neutral' },
}

// `expired` and `failed` read a reason and then a recourse (§3). The recourse is dropped for an
// objecting owner (T729): no upload is offered under it, so the sentence would promise one.
const EXPIRED_FIRST_SENTENCE = 'The replay existed, but we did not capture it in time.'
const FAILED_FIRST_SENTENCE = 'We could not capture this replay after repeated attempts.'
const UPLOAD_RECOURSE = 'If you still have the file, you can upload it.'

// The three "Lost" statuses and "Needs review" carry the *reason* as SecondaryLine, because they
// send the user to different places (§3). `stored` has none: "Archived" needs no further sentence.
// These four read the same in both variants.
const REASON: Partial<Record<CaptureStatus, string>> = {
  unavailable:
    'The game never recorded this match. Your own saved games folder is probably empty too.',
  expired: `${EXPIRED_FIRST_SENTENCE} ${UPLOAD_RECOURSE}`,
  failed: `${FAILED_FIRST_SENTENCE} ${UPLOAD_RECOURSE}`,
  quarantined:
    'We have a copy, but it failed validation. It is kept for review — there is nothing further for you to do.',
}

// `withdrawn` is the one reason that depends on the variant (§3): `detail` carries the sentence,
// `compact` shows the pill alone, because one sentence repeated down an objector's list would be
// the red banner `archival-control.md` §4.3 rules out, in small print. The sentence claims nothing
// about the deadline, the source, what the row holds or what to do next (§3).
const DETAIL_ONLY_REASON: Partial<Record<CaptureStatus, string>> = {
  withdrawn:
    'Automatic capture ended for this match while archival was not running for this profile.',
}

// T729 (§3): what an objecting owner's `expired`/`failed` row reads — the first sentence alone.
const REASON_WITHOUT_RECOURSE: Partial<Record<CaptureStatus, string>> = {
  expired: EXPIRED_FIRST_SENTENCE,
  failed: FAILED_FIRST_SENTENCE,
}

// T724 (§3): the one fact the session holds for an objecting owner's catchable row. It claims
// nothing about the deadline or about what resuming archival would recover.
const ARCHIVAL_OFF_SENTENCE = 'Archival is off for your account.'

const CATCHABLE = new Set<CaptureStatus>(['pending', 'downloading'])

// "Recomputed on an interval no coarser than once per minute while mounted"
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
  variant: CaptureStateBadgeVariant,
  archivalObjected: boolean,
): string | undefined {
  if (CATCHABLE.has(status)) {
    // "Never a countdown built from a missing value" (§6) — should not happen per data-model.md,
    // but a missing deadline renders the pill with no SecondaryLine rather than trusted blindly.
    return deadlineAt ? describeCaptureCountdown(deadlineAt, now, variant) : undefined
  }
  // T729 (§3): the objecting owner is offered no upload, so `expired`/`failed` drop that sentence.
  if (archivalObjected && status in REASON_WITHOUT_RECOURSE) return REASON_WITHOUT_RECOURSE[status]
  return REASON[status] ?? (variant === 'detail' ? DETAIL_ONLY_REASON[status] : undefined)
}

/** Maps `replay_captures.status`'s eight raw values and `archivalObjected` to what a user sees;
 * a caller passes neither a label nor a tone — see capture-state-badge.md §3, §4. */
export function CaptureStateBadge({
  captureStatus,
  captureDeadlineAt = null,
  archivalObjected = false,
  variant = 'compact',
  stacked = false,
  loading = false,
  className,
}: CaptureStateBadgeProps) {
  const isCatchable = captureStatus != null && CATCHABLE.has(captureStatus as CaptureStatus)
  // T724 (§3, §7): an objecting owner's catchable row shows no countdown, so nothing ticks for it.
  const archivalOff = archivalObjected && isCatchable
  const now = useTickingNow(!loading && isCatchable && !archivalOff)
  const secondaryId = useId()

  if (loading) {
    // Pill footprint: `space-5` tall, ~90px wide (§6) — `w-24` (space scale) is the closest
    // token-backed step to that approximation; there is no dedicated pill-width token.
    // `variant="block"` (not `text`): `text` ignores the caller's size and varies its own width
    // for a paragraph line, which is wrong for a single pill's fixed footprint.
    return <Skeleton variant="block" className={cx('h-5 w-24', className)} />
  }

  if (!captureStatus) return null

  // The objecting owner's catchable row renders as `withdrawn` does (§3).
  const known = archivalOff
    ? TONE_BY_STATUS.withdrawn
    : TONE_BY_STATUS[captureStatus as CaptureStatus]

  if (!known) {
    // Forward-compatibility guard (§6 "error"): a status this component cannot classify still
    // reads as a word, never a blank pill and never a guessed tone.
    return <Badge variant="neutral">{captureStatus}</Badge>
  }

  const secondary = archivalOff
    ? variant === 'detail'
      ? ARCHIVAL_OFF_SENTENCE
      : undefined
    : secondaryLineFor(
        captureStatus as CaptureStatus,
        captureDeadlineAt,
        now,
        variant,
        archivalObjected,
      )

  // `detail` always stacks, `space-1` between pill and SecondaryLine (§4, §9). `compact` stacks
  // either because the caller told it to (`stacked` — a box it knows is bounded, like MatchRow's
  // trailing table column) or, absent that, by its own best guess from the window's width (§10) —
  // right for a full-width card, wrong for a bounded column, which is exactly why `stacked`
  // exists. Both compact cases keep `space-2` (§9's own "inline, compact" row; no dedicated
  // "stacked, compact" row exists, so this reuses the one pair the spec already gives compact).
  const layoutClassName =
    variant === 'detail'
      ? 'flex-col items-start gap-1'
      : cx('flex-col items-start gap-2', !stacked && 'sm:flex-row sm:items-center')

  return (
    <div className={cx('flex', layoutClassName, className)}>
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
