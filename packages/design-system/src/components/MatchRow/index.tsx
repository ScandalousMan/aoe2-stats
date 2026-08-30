import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { CaptureStateBadge } from '../CaptureStateBadge'
import { Skeleton } from '../Skeleton'
import { StatValue } from '../StatValue'
import type { StatValueDelta } from '../StatValue'

// packages/design-system/specs/match-history.md

/** Shared by `MatchRow.outcome` and `MatchDetailPanel`'s `ParticipantData.result` (imported there
 * from here, mirroring how both components already share `StatValueDelta` from `StatValue`) —
 * `"unknown"` is not a fallback spelling of `"loss"`: it is the state a `result` this service has
 * not yet recorded (`match_players.result` is `null` for every row today — `discover.py`'s own
 * docstring) must render as, per match-history.md §2a. `apps/web/src/features/matches/format.ts`'s
 * `formatOutcome` is the one place a wire `result` becomes this union. */
export type MatchOutcome = 'win' | 'loss' | 'unknown'

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
  outcome: MatchOutcome
  opponent: MatchRowOpponent
  map: ReactNode
  /** The caller's own civilisation for this match — text only for now. Constitution X 5.0.0 no
   * longer bans a civilisation icon here; this feature (004) widens `MatchRow` to take one in a
   * later phase, not yet landed. */
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
  /** Wires this row's click into the caller's own router (T388), the same seam
   * `PlayerResultRow.onNavigate` defines — the row stays a real `<a href={match.href}>`, a
   * modified click or the absence of `onNavigate` falls through to native handling. */
  onNavigate?: (href: string) => void
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

// match-history.md §2a: "Win"/"Loss" assert a fact this service has; "Unknown" (`text-secondary`,
// never `success`/`danger`) is the one state that does not, and reads as a gap by wording alone —
// never colour alone (constitution VI).
const OUTCOME_LABEL_TEXT: Record<MatchOutcome, string> = {
  win: 'Win',
  loss: 'Loss',
  unknown: 'Unknown',
}

const OUTCOME_LABEL_TONE: Record<MatchOutcome, string> = {
  win: 'text-success',
  loss: 'text-danger',
  unknown: 'text-secondary',
}

function OutcomeLabel({ outcome }: { outcome: MatchOutcome }) {
  return (
    <span className={cx('font-sans text-sm font-semibold', OUTCOME_LABEL_TONE[outcome])}>
      {OUTCOME_LABEL_TEXT[outcome]}
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
export function MatchRow({ match, onNavigate, className }: MatchRowProps) {
  return (
    <a
      href={match.href}
      onClick={createRowLinkClickHandler(match.href, onNavigate)}
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

/** match-history.md §11.3: which player's history this list is — the row itself never differs
 * (`MatchRow` above takes no `subject` of its own), only the two fixed strings around it that
 * presuppose the viewer is the subject: the table's own `<caption>` and the empty-state sentence.
 * Mirrors `ProfileSummarySubject` (`ProfileSummary`), the identical read this component's own page
 * header already uses for the header above this list. */
export type MatchListSubject = 'self' | 'other'

export interface MatchListProps {
  status?: MatchListStatus
  matches?: MatchRowData[]
  onRetry?: () => void
  /** Forwarded, unchanged, to every `MatchRow` in the card layout and every row link in the table
   * layout (T388) — see `MatchRowProps.onNavigate`. */
  onNavigate?: (href: string) => void
  /** Defaults to `'self'`, preserving this component's original copy unchanged for
   * `matches.index.tsx` (T075) — the caller's own history. `'other'` swaps §11.3's two strings for
   * a third party's, read from `subjectAlias`. */
  subject?: MatchListSubject
  /** The viewed player's alias, spliced into §11.3's two `subject="other"` strings. A plain
   * `string`, not `ReactNode` — one of these two strings is also this component's own `<ul>`
   * `aria-label` (§9's accessible list name), which cannot take a JSX child. Ignored for
   * `subject="self"` (default), and never required there — the caller's own list names no alias
   * in either string it uses. */
  subjectAlias?: string
  className?: string
}

/** The list of matches: reverse-chronological, one DOM per viewport (never both a table and a
 * card list at once — §8), plus the list's own loading/error/empty states (§5). Consumed by
 * `apps/web/src/routes/matches.index.tsx` (T075), which supplies the page header above it. */
export function MatchList({
  status = 'default',
  matches = [],
  onRetry,
  onNavigate,
  subject = 'self',
  subjectAlias,
  className,
}: MatchListProps) {
  // §8 reserves everything below 1280 for cards; `xl` is the named breakpoint at that width
  // (`lg` is 1024 — see `useMediaQuery.ts`'s own DS-5 table), not `lg`.
  const isTable = useBreakpoint('xl')

  // §11.3: the one fixed string that presupposes the viewer is the subject, computed once here
  // rather than at each of its two call sites below — the table `<caption>` and the `<ul>`'s own
  // `aria-label` (§9, §11.5: "screen-reader users get the corrected subject the same way sighted
  // users do, from the same string").
  const caption = subject === 'other' ? `${subjectAlias}'s recent matches` : 'Your recent matches'

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
          <Button variant="primary" size="lg" onClick={onRetry}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  if (status === 'empty' || matches.length === 0) {
    // §11.3: "the empty state is a fact about the player, stated once" — a single sentence for
    // `subject="other"`, never the first-person heading+body pair `subject="self"` keeps below.
    if (subject === 'other') {
      return (
        <Callout
          tone="info"
          heading={`${subjectAlias} has no matches in their history yet.`}
          className={className}
        />
      )
    }
    return (
      <Callout tone="info" heading="No matches yet" className={className}>
        Once you play, they will appear here.
      </Callout>
    )
  }

  if (isTable) {
    return (
      <MatchTable
        matches={matches}
        onNavigate={onNavigate}
        caption={caption}
        className={className}
      />
    )
  }

  return (
    <ul className={cx('flex flex-col gap-3', className)} aria-label={caption}>
      {matches.map((match) => (
        <li key={match.gameId}>
          <MatchRow match={match} onNavigate={onNavigate} />
        </li>
      ))}
    </ul>
  )
}

function MatchTable({
  matches,
  onNavigate,
  caption,
  className,
}: {
  matches: MatchRowData[]
  onNavigate?: (href: string) => void
  caption: string
  className?: string
}) {
  return (
    <table className={cx('w-full border-collapse text-left font-sans text-sm', className)}>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-border">
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Result
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Opponent
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Map
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Civilisation
          </th>
          <th scope="col" className="py-3 pr-5 text-right font-normal text-text-secondary">
            Change
          </th>
          <th scope="col" className="py-3 pr-5 text-right font-normal text-text-secondary">
            Duration
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            When
          </th>
          <th scope="col" className="py-3 font-normal text-text-secondary">
            Capture
          </th>
        </tr>
      </thead>
      <tbody>
        {matches.map((match) => (
          <MatchTableRow key={match.gameId} match={match} onNavigate={onNavigate} />
        ))}
      </tbody>
    </table>
  )
}

// A `<tr>` cannot itself be an `<a>`, so the row's single link lives in one cell and is stretched
// over the whole row with `after:absolute after:inset-0` against the row's own `relative` — the
// standard "one link, whole row clickable" technique, keeping exactly one focus stop (§9).
function MatchTableRow({
  match,
  onNavigate,
}: {
  match: MatchRowData
  onNavigate?: (href: string) => void
}) {
  return (
    <tr className="group relative border-b border-border transition-colors duration-120 ease-standard hover:bg-surface-sunken">
      <th scope="row" className="py-3 pr-5 font-normal">
        <a
          href={match.href}
          onClick={createRowLinkClickHandler(match.href, onNavigate)}
          className={cx(
            'static font-sans text-sm font-semibold after:absolute after:inset-0',
            focusRing,
            OUTCOME_LABEL_TONE[match.outcome],
          )}
        >
          {OUTCOME_LABEL_TEXT[match.outcome]}
        </a>
      </th>
      <td className="py-3 pr-5 text-text-primary">
        <OpponentLabel opponent={match.opponent} />
      </td>
      <td className="py-3 pr-5 text-text-primary">{match.map}</td>
      <td className="py-3 pr-5 text-text-primary">{match.civilisation}</td>
      <td className="py-3 pr-5 text-right font-mono text-sm">
        {match.ratingChange && <TableRatingChange delta={match.ratingChange} />}
      </td>
      <td className="py-3 pr-5 text-right font-mono text-text-primary">{match.durationLabel}</td>
      <td className="py-3 pr-5 text-text-secondary" title={match.playedAtAbsolute}>
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
