import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { CaptureStateBadge } from '../CaptureStateBadge'
import { Skeleton } from '../Skeleton'
import { StatValue } from '../StatValue'
import type { StatValueDelta } from '../StatValue'

// packages/design-system/specs/match-history.md

export interface MatchRowOpponent {
  /** The first opposing-team participant's alias (§4). */
  alias: string
  /** Team matches only: the count of opposing-team participants not named by `alias`. Absent or 0
   * for a 1v1 — never a bare count with no name (§4). */
  othersCount?: number
}

export interface MatchRowData {
  gameId: string
  /** The match detail route (T076's `matches.$gameId.tsx`). `MatchRow` never invents this path. */
  href: string
  outcome: 'win' | 'loss'
  opponent: MatchRowOpponent
  map: ReactNode
  /** The caller's own civilisation for this match — factual name only, no emblem (§2 IP note). */
  civilisation: ReactNode
  /** Absent when the match carries no rating change to report. */
  ratingChange?: StatValueDelta
  /** Pre-formatted — "34 min", never raw seconds (§2). */
  durationLabel: ReactNode
  /** Pre-formatted relative time — "3 hours ago" (§2). */
  playedAtRelative: ReactNode
  /** Absolute date/time, shown on hover/focus via the native `title` tooltip (§2). */
  playedAtAbsolute?: string
  captureStatus?: string | null
  captureDeadlineAt?: string | null
}

export interface MatchRowProps {
  match: MatchRowData
  className?: string
}

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring'

function OpponentLabel({ opponent }: { opponent: MatchRowOpponent }) {
  return (
    <span className="font-sans text-sm text-text-primary">
      {opponent.alias}
      {opponent.othersCount ? ` and ${opponent.othersCount} others` : ''}
    </span>
  )
}

function OutcomeLabel({ outcome }: { outcome: 'win' | 'loss' }) {
  const won = outcome === 'win'
  return (
    <span className={cx('font-sans text-sm font-semibold', won ? 'text-success' : 'text-danger')}>
      {won ? 'Win' : 'Loss'}
    </span>
  )
}

function MatchMeta({ match }: { match: MatchRowData }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-xs text-text-secondary">
      <span>{match.map}</span>
      <span aria-hidden="true">·</span>
      <span>{match.civilisation}</span>
      <span aria-hidden="true">·</span>
      <span>{match.durationLabel}</span>
      <span aria-hidden="true">·</span>
      <span title={match.playedAtAbsolute}>{match.playedAtRelative}</span>
    </div>
  )
}

/** One match, the whole card is a single link (§2, §9): everything inside — including
 * `CaptureStateBadge` — is non-interactive text, so the row has exactly one focus stop. Used
 * directly below `xl`; `MatchList` renders a real `<table>` above it instead (§8). */
export function MatchRow({ match, className }: MatchRowProps) {
  return (
    <a
      href={match.href}
      className={cx(
        'flex flex-col gap-2 rounded-lg border border-border bg-surface p-4',
        'transition-colors duration-120 ease-standard hover:bg-surface-sunken',
        focusRing,
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <OutcomeLabel outcome={match.outcome} />
          <OpponentLabel opponent={match.opponent} />
        </div>
        {match.ratingChange && (
          <StatValue variant="inline" label="Rating change" delta={match.ratingChange} />
        )}
      </div>
      <MatchMeta match={match} />
      <CaptureStateBadge
        context="compact"
        captureStatus={match.captureStatus}
        captureDeadlineAt={match.captureDeadlineAt}
      />
    </a>
  )
}

export type MatchListStatus = 'default' | 'loading' | 'error' | 'empty'

export interface MatchListProps {
  status?: MatchListStatus
  matches?: MatchRowData[]
  onRetry?: () => void
  className?: string
}

/** The list of matches: reverse-chronological, one DOM per viewport (never both a table and a
 * card list at once — §8), plus the list's own loading/error/empty states (§5). Consumed by
 * `apps/web/src/routes/matches.index.tsx` (T075), which supplies the page header above it. */
export function MatchList({
  status = 'default',
  matches = [],
  onRetry,
  className,
}: MatchListProps) {
  // §8 reserves everything below 1280 for cards; `xl` is the named breakpoint at that width
  // (`lg` is 1024 — see `useMediaQuery.ts`'s own DS-5 table), not `lg`.
  const isTable = useBreakpoint('xl')

  if (status === 'loading') {
    return (
      <div className={cx('flex flex-col gap-3', className)} aria-busy="true">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} variant="block" className="h-24 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <Callout
        tone="danger"
        heading="We could not load your match history"
        actions={
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  if (status === 'empty' || matches.length === 0) {
    return (
      <Callout tone="info" heading="No matches yet" className={className}>
        Once you play, they will appear here.
      </Callout>
    )
  }

  if (isTable) {
    return <MatchTable matches={matches} className={className} />
  }

  return (
    <ul className={cx('flex flex-col gap-3', className)}>
      {matches.map((match) => (
        <li key={match.gameId}>
          <MatchRow match={match} />
        </li>
      ))}
    </ul>
  )
}

function MatchTable({ matches, className }: { matches: MatchRowData[]; className?: string }) {
  return (
    <table className={cx('w-full border-collapse text-left font-sans text-sm', className)}>
      <caption className="sr-only">Your recent matches</caption>
      <thead>
        <tr className="border-b border-border">
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            Result
          </th>
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            Opponent
          </th>
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            Map
          </th>
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            Civilisation
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Change
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Duration
          </th>
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            When
          </th>
          <th scope="col" className="py-3 font-normal text-text-secondary">
            Capture
          </th>
        </tr>
      </thead>
      <tbody>
        {matches.map((match) => (
          <MatchTableRow key={match.gameId} match={match} />
        ))}
      </tbody>
    </table>
  )
}

// A `<tr>` cannot itself be an `<a>`, so the row's single link lives in one cell and is stretched
// over the whole row with `after:absolute after:inset-0` against the row's own `relative` — the
// standard "one link, whole row clickable" technique, keeping exactly one focus stop (§9).
function MatchTableRow({ match }: { match: MatchRowData }) {
  const won = match.outcome === 'win'
  return (
    <tr className="group relative border-b border-border transition-colors duration-120 ease-standard hover:bg-surface-sunken">
      <th scope="row" className="py-3 pr-6 font-normal">
        <a
          href={match.href}
          className={cx(
            'static font-sans text-sm font-semibold after:absolute after:inset-0',
            focusRing,
            won ? 'text-success' : 'text-danger',
          )}
        >
          {won ? 'Win' : 'Loss'}
        </a>
      </th>
      <td className="py-3 pr-6 text-text-primary">
        <OpponentLabel opponent={match.opponent} />
      </td>
      <td className="py-3 pr-6 text-text-primary">{match.map}</td>
      <td className="py-3 pr-6 text-text-primary">{match.civilisation}</td>
      <td className="py-3 pr-6 text-right font-mono text-sm">
        {match.ratingChange && <TableRatingChange delta={match.ratingChange} />}
      </td>
      <td className="py-3 pr-6 text-right font-mono text-text-primary">{match.durationLabel}</td>
      <td className="py-3 pr-6 text-text-secondary" title={match.playedAtAbsolute}>
        {match.playedAtRelative}
      </td>
      <td className="py-3">
        {/* `stacked`: this column's width is bounded by the table, not by the window
         * (match-history.md §8) — told to stack rather than left to infer a container width the
         * badge cannot observe (§8, capture-state-badge.md's own `stacked` prop). */}
        <CaptureStateBadge
          context="compact"
          stacked
          captureStatus={match.captureStatus}
          captureDeadlineAt={match.captureDeadlineAt}
        />
      </td>
    </tr>
  )
}

// Mirrors `ProfileSummary`'s own `RatingTable` cell, the established precedent for a table cell
// that needs the same signed-delta look `StatValue`'s `delta` slot renders, without the `<dl>`
// structure a table cell cannot use.
function TableRatingChange({ delta }: { delta: StatValueDelta }) {
  const positive = delta.value >= 0
  const magnitude = delta.formatted ?? String(Math.abs(delta.value))
  return (
    <span className={cx('font-mono font-semibold', positive ? 'text-success' : 'text-danger')}>
      {positive ? '+' : '−'}
      {magnitude}
    </span>
  )
}
