import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { CaptureStateBadge } from '../CaptureStateBadge'
import { Skeleton } from '../Skeleton'
import type { StatValueDelta } from '../StatValue'

// packages/design-system/specs/match-history.md

export interface ParticipantData {
  id: string
  alias: ReactNode
  civilisation: ReactNode
  result: 'win' | 'loss'
  /** Absent when the match carries no rating change to report for this participant. */
  ratingChange?: StatValueDelta
}

export interface TeamGroupData {
  id: string
  /** e.g. "Team 1". Named once and reused as both the visible heading and the table's own
   * visually hidden `<caption>` — never invented twice (§9). */
  name: ReactNode
  participants: ParticipantData[]
}

export interface MatchDetailData {
  gameId: string
  map: ReactNode
  leaderboardName: ReactNode
  /** Pre-formatted — "34 min", never raw seconds. */
  durationLabel: ReactNode
  /** Pre-formatted played-on date/time. */
  playedAtLabel: ReactNode
  captureStatus?: string | null
  captureDeadlineAt?: string | null
  teams: TeamGroupData[]
}

export type MatchDetailStatus = 'default' | 'loading' | 'error' | 'not-found'
export type DownloadActionState = 'idle' | 'loading' | 'error'

export interface MatchDetailPanelProps {
  status?: MatchDetailStatus
  match?: MatchDetailData
  downloadState?: DownloadActionState
  onDownload?: () => void
  onRetry?: () => void
  /** Where "back to the match list" points. Defaults to `/matches` (T075's route). */
  matchListHref?: string
  className?: string
}

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

function ResultLabel({ result }: { result: 'win' | 'loss' }) {
  const won = result === 'win'
  return (
    <span className={cx('font-sans text-sm font-semibold', won ? 'text-success' : 'text-danger')}>
      {won ? 'Win' : 'Loss'}
    </span>
  )
}

/** Everything about one match, and the one action a `stored` replay is for. `status="loading"`
 * needs no `match` at all; every other status requires one. */
export function MatchDetailPanel({
  status = 'default',
  match,
  downloadState = 'idle',
  onDownload,
  onRetry,
  matchListHref = '/matches',
  className,
}: MatchDetailPanelProps) {
  if (status === 'error') {
    return (
      <Callout
        tone="danger"
        heading="We could not load this match"
        actions={
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  // "Not found" covers both an unknown game id and a real match that is not the caller's own —
  // the two must never be distinguishable to the caller (FR-045).
  if (status === 'not-found') {
    return (
      <Callout
        tone="danger"
        heading="This match could not be found."
        actions={
          <Button variant="secondary" href={matchListHref}>
            Back to the match list
          </Button>
        }
        className={className}
      />
    )
  }

  if (status === 'loading' || !match) {
    return (
      <div className={cx('flex flex-col gap-6', className)} aria-busy="true">
        <header className="flex flex-col gap-2">
          <Skeleton variant="text" lines={1} className="w-48" />
          <Skeleton variant="text" lines={1} className="w-64" />
          <CaptureStateBadge context="detail" loading />
        </header>
        <div className="flex flex-col gap-3">
          <Skeleton variant="block" className="h-14 w-full rounded-lg" />
          <Skeleton variant="block" className="h-14 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className={cx('flex flex-col gap-6', className)}>
      <header className="flex flex-col gap-3">
        <div>
          {/* `<h2>`, not `<h1>`: this panel is a section of a page that already carries its own
           * page-level heading (T076's route) — matching `Callout`'s own "keeps a sane outline"
           * reasoning for a component that is always nested. */}
          <h2 className="font-display text-xl font-semibold text-text-primary">{match.map}</h2>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {match.leaderboardName}
            <span aria-hidden="true"> · </span>
            {match.durationLabel}
            <span aria-hidden="true"> · </span>
            {match.playedAtLabel}
          </p>
        </div>
        <CaptureStateBadge
          context="detail"
          captureStatus={match.captureStatus}
          captureDeadlineAt={match.captureDeadlineAt}
        />
      </header>

      {match.captureStatus === 'stored' && (
        <Button
          variant="secondary"
          loading={downloadState === 'loading'}
          loadingLabel="Preparing your download…"
          onClick={onDownload}
          className="self-start"
        >
          Download replay
        </Button>
      )}

      {downloadState === 'error' && (
        <Callout tone="danger" heading="The download link could not be created. Try again." />
      )}

      <ParticipantsTable teams={match.teams} />
    </div>
  )
}

function ParticipantsTable({ teams }: { teams: TeamGroupData[] }) {
  return (
    <div className="flex flex-col gap-5">
      {teams.map((team) => (
        <TeamGroup key={team.id} team={team} />
      ))}
    </div>
  )
}

function TeamGroup({ team }: { team: TeamGroupData }) {
  // §8 names three tiers: 375 one card per participant, 768 two participants side by side, 1280 a
  // real table. `xl` is the named breakpoint for the table (`lg` is 1024, reserved by §8 for
  // cards — see `useMediaQuery.ts`'s own DS-5 table); `md` (768) is the middle tier.
  const isTable = useBreakpoint('xl')
  const isTwoColumn = useBreakpoint('md')
  const headingId = `match-detail-team-${team.id}`

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="mb-2 font-sans text-sm font-semibold text-text-secondary">
        {team.name}
      </h3>
      {isTable ? (
        <table className="w-full border-collapse text-left font-sans text-sm">
          <caption className="sr-only">{team.name}</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="py-2 pr-4 font-normal text-text-secondary">
                Player
              </th>
              <th scope="col" className="py-2 pr-4 font-normal text-text-secondary">
                Civilisation
              </th>
              <th scope="col" className="py-2 pr-4 font-normal text-text-secondary">
                Result
              </th>
              <th scope="col" className="py-2 text-right font-normal text-text-secondary">
                Change
              </th>
            </tr>
          </thead>
          <tbody>
            {team.participants.map((participant) => (
              <tr key={participant.id} className="border-b border-border">
                <th scope="row" className="py-2 pr-4 font-normal text-text-primary">
                  {participant.alias}
                </th>
                <td className="py-2 pr-4 text-text-primary">{participant.civilisation}</td>
                <td className="py-2 pr-4">
                  <ResultLabel result={participant.result} />
                </td>
                <td className="py-2 text-right font-mono text-sm">
                  {participant.ratingChange && (
                    <TableRatingChange delta={participant.ratingChange} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        // §8's 768 tier: two participants side by side within a `TeamGroup`, still cards (never
        // a table below `xl`). `gap-2` reused rather than a new column-gap value invented for a
        // register match-history.md §7 does not name.
        <ul className={isTwoColumn ? 'grid grid-cols-2 gap-2' : 'flex flex-col gap-2'}>
          {team.participants.map((participant) => (
            <li
              key={participant.id}
              className="flex flex-col gap-1 rounded-lg border border-border p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-sans text-sm font-semibold text-text-primary">
                  {participant.alias}
                </span>
                <ResultLabel result={participant.result} />
              </div>
              <div className="flex items-center justify-between gap-3 font-sans text-xs text-text-secondary">
                <span>{participant.civilisation}</span>
                {participant.ratingChange && <TableRatingChange delta={participant.ratingChange} />}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
