import type { ReactNode } from 'react'
import { useEffect, useId, useState } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Badge } from '../Badge'
import type { BadgeVariant } from '../Badge'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { describeCaptureCountdown } from '../CaptureStateBadge/countdown'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/replay-availability.md

/** FR-025's four, exactly — never collapsed the way `CaptureStateBadge` collapses its own seven
 * raw statuses (§3: "the four states never share a label"). */
export type ReplayAvailability = 'archived' | 'obtainable' | 'expired' | 'never_recorded'

/** The state of this row's own download attempt — independent of `availability`. `idle` covers
 * both "never tried" and "tried, then returned to default" (§5's own rule: a failed attempt
 * returns the button to default and pressable, it never becomes a dead end). */
export type ReplayDownloadState = 'idle' | 'loading' | 'error' | 'rate_limited'

export interface ReplayAvailabilityRowData {
  /** React list key and the id `onDownload` is called with — never rendered. */
  id: string
  alias: ReactNode
  availability: ReplayAvailability
  /** ISO 8601, or `null`/absent. FR-024, amended 2026-08-29: `null` in every state until the
   * retention window is settled (§3.2) — consulted only while `availability === 'obtainable'`,
   * and only ever handed to `describeCaptureCountdown` when it is not `null` (§3.2, the same
   * "caller checks first" contract that function already has with `CaptureStateBadge`). */
  obtainableUntil?: string | null
  /** True for exactly one page load: this row was rendered `obtainable` and its download 404'd at
   * fetch time (`code: "expired_since_page_load"`, `contracts/http-api.md` §"boundary race").
   * Never true for a row that loaded already `expired` — that row uses §3.1's plain sentence
   * instead. Ignored unless `availability === 'expired'`. */
  expiredSincePageLoad?: boolean
  /** Defaults to `'idle'`. */
  downloadState?: ReplayDownloadState
  /** Present when `downloadState === 'rate_limited'` **and** the caller has a figure to give — the
   * exact seconds the response carried, never rounded or invented (§5). Not required even then:
   * `rate_limited` has two distinct causes, and only one carries a `retry_after` to pass on. This
   * service's own per-caller limit (FR-028, `_apply_replay_download_rate_limit`) knows its own
   * `retry_after`. The replay source refusing this service's own request (`_source_rate_limited_error`,
   * a 403/429 from `aoe.ms`) does not — `aoe.ms` gives this service no figure to relay — so that cause
   * reaches `rate_limited` with this prop `undefined`, and §5's rendering already falls back to the
   * generic failed-request copy for that case (this component's own null-check below, unchanged). */
  retryAfterSeconds?: number
}

export interface ReplayAvailabilityListProps {
  /** Same participant order as `ParticipantsTable` (`match-history.md` §2, `replay-availability.md`
   * §2) — grouped by team, so a reader can correlate a name to its download status without
   * re-scanning against the table above it. This component does not itself group or reorder: the
   * caller supplies participants in that order. */
  rows?: ReplayAvailabilityRowData[]
  /** The match detail response has not arrived yet (§5 "loading"). Takes priority over `rows`. */
  loading?: boolean
  onDownload?: (rowId: string) => void
  className?: string
}

// §3 — one label and one tone per state, never chosen by the caller. `expired` and
// `never_recorded` differ in tone (danger vs neutral), not only in label (§3's own "belt and
// braces" note); `archived` and `obtainable` differ too (success vs info), even though both show a
// `DownloadAction`.
const STATE_META: Record<ReplayAvailability, { label: string; variant: BadgeVariant }> = {
  archived: { label: 'In our archive', variant: 'success' },
  obtainable: { label: 'Obtainable', variant: 'info' },
  expired: { label: 'Expired', variant: 'danger' },
  never_recorded: { label: 'Never recorded', variant: 'neutral' },
}

// §3.1 — exact strings, not placeholders. Neither implies fault or invites an upload (FR-027);
// neither promises the fact could ever have been otherwise.
const EXPIRED_REASON = 'This recording is no longer available from the game.'
const NEVER_RECORDED_REASON = 'The game did not record this point of view.'
// §5 "the boundary race" — distinct from `EXPIRED_REASON` above: the recording existed a moment
// ago, which the plain "no longer available" sentence does not say and `never_recorded`'s wording
// would misstate outright.
const EXPIRED_SINCE_PAGE_LOAD_REASON = 'This recording expired while you were viewing this page.'

const DOWNLOAD_START_FAILED = 'We could not start that download. Try again.'

function rateLimitMessage(retryAfterSeconds: number): string {
  const unit = retryAfterSeconds === 1 ? 'second' : 'seconds'
  return `You are downloading too quickly. Try again in ${retryAfterSeconds} ${unit}.`
}

// §6 "recomputed on an interval no coarser than once per minute while the row is mounted" — the
// identical cadence `CaptureStateBadge` keeps for its own countdown (`countdown.ts`'s own module
// note: the ticking clock is the component's, not the pure function's). Only ticks while at least
// one row actually has a countdown to show, so a list with no dated `obtainable` row never
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

// §6's last bullet: a passed `obtainableUntil` on an `obtainable` row means the row's displayed
// state has gone stale, not that a countdown is approaching zero — `describeCaptureCountdown`'s
// own "window closing" sentence names *capture*, which is wrong here in both process and fact, so
// it is never rendered. The row shows no `SecondaryLine` at all for that one interval instead.
function secondaryLineFor(row: ReplayAvailabilityRowData, now: number): string | undefined {
  switch (row.availability) {
    case 'archived':
      return undefined
    case 'obtainable': {
      if (!row.obtainableUntil) return undefined
      const remainingMs = new Date(row.obtainableUntil).getTime() - now
      if (remainingMs <= 0) return undefined
      return describeCaptureCountdown(row.obtainableUntil, now, 'compact')
    }
    case 'expired':
      return row.expiredSincePageLoad ? EXPIRED_SINCE_PAGE_LOAD_REASON : EXPIRED_REASON
    case 'never_recorded':
      return NEVER_RECORDED_REASON
  }
}

// §5 "loading" — 2 `Skeleton/block` rows, the same smallest-known-participant-count rule
// `match-history.md` §5 states for `ParticipantsTable`.
const LOADING_ROW_IDS = ['loading-row-1', 'loading-row-2']

/** Per match, one row per participant, stating whether their recorded game can be had right now —
 * and never letting an unobtainable one render as a button that then fails (FR-025). See
 * `packages/design-system/specs/replay-availability.md`. */
export function ReplayAvailabilityList({
  rows = [],
  loading = false,
  onDownload,
  className,
}: ReplayAvailabilityListProps) {
  const headingId = useId()
  const hasCountdown = rows.some((row) => row.availability === 'obtainable' && row.obtainableUntil)
  const now = useTickingNow(!loading && hasCountdown)

  return (
    <section aria-labelledby={headingId} className={cx('flex flex-col', className)}>
      <h3 id={headingId} className="font-sans text-md font-semibold text-text-primary">
        Recorded games
      </h3>
      <ul className="mt-4 flex flex-col gap-3">
        {loading
          ? LOADING_ROW_IDS.map((id) => (
              <li key={id}>
                <Skeleton variant="block" className="h-14 w-full rounded-lg" />
              </li>
            ))
          : rows.map((row) => (
              <ReplayAvailabilityRow key={row.id} row={row} now={now} onDownload={onDownload} />
            ))}
      </ul>
    </section>
  )
}

function ReplayAvailabilityRow({
  row,
  now,
  onDownload,
}: {
  row: ReplayAvailabilityRowData
  now: number
  onDownload?: (rowId: string) => void
}) {
  // §9: 375 stacks the whole row (label+badge, then SecondaryLine, then a full-width
  // DownloadAction); 768 sits everything on one line and DownloadAction becomes intrinsic-width,
  // right-aligned. 1280 is unchanged from 768 (§9: "does not gain a `<table>` layout").
  const isMd = useBreakpoint('md')
  const secondaryId = useId()
  const meta = STATE_META[row.availability]
  const secondary = secondaryLineFor(row, now)
  // §3: present only for `archived` and `obtainable`, absent — never disabled — otherwise (§5).
  const canDownload = row.availability === 'archived' || row.availability === 'obtainable'
  const downloadState = row.downloadState ?? 'idle'
  const showFailure = downloadState === 'error' || downloadState === 'rate_limited'

  return (
    <li className="flex flex-col gap-4">
      <div
        className={cx('flex flex-col gap-4', isMd && 'flex-row items-center justify-between gap-4')}
      >
        <div className={cx('flex flex-col gap-1', isMd && 'flex-row items-center gap-3')}>
          <div className="flex items-center gap-3">
            <span className="font-sans text-sm text-text-primary">{row.alias}</span>
            <span aria-describedby={secondary ? secondaryId : undefined}>
              <Badge variant={meta.variant}>{meta.label}</Badge>
            </span>
          </div>
          {secondary && (
            <span id={secondaryId} className="font-sans text-sm text-text-secondary">
              {secondary}
            </span>
          )}
        </div>
        {canDownload && (
          // `size="lg"`, never `md`: this button is reachable on a touch viewport (§9's 375
          // tier), and `Button`'s own doc reserves `md` for pointer-only placements — the same
          // reasoning `MatchDetailPanel`'s own `DownloadAction` already follows.
          <Button
            variant="secondary"
            size="lg"
            loading={downloadState === 'loading'}
            loadingLabel="Preparing your download…"
            onClick={() => onDownload?.(row.id)}
            className={cx(!isMd && 'w-full', isMd && 'shrink-0')}
          >
            Download
          </Button>
        )}
      </div>
      {showFailure && (
        <Callout
          tone="danger"
          // Nested one level below this list's own `<h3>` heading (§10's `<section
          // aria-labelledby>`), so the outline stays `h3` -> `h4` rather than jumping back to `h2`.
          headingLevel={4}
          heading={
            downloadState === 'rate_limited' && row.retryAfterSeconds != null
              ? rateLimitMessage(row.retryAfterSeconds)
              : DOWNLOAD_START_FAILED
          }
        />
      )}
    </li>
  )
}
