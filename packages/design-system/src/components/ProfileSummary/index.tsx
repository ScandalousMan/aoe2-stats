import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Badge } from '../Badge'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { Menu } from '../Menu'
import type { MenuItem } from '../Menu'
import { Skeleton } from '../Skeleton'
import { StatValue } from '../StatValue'

// packages/design-system/specs/profile-summary.md

export type ProfileSummaryVariant = 'board' | 'compact'

export interface LinkedProfileOption {
  id: string
  alias: string
  isPrimary: boolean
}

export interface RatingEntryData {
  leaderboardId: string
  leaderboardName: string
  rating: string
  ratingDelta?: { value: number; formatted?: string }
  /** `undefined` — a played leaderboard with a rating but no rank yet (provisional). */
  rank?: string
  wins: number
  losses: number
  winRate?: string
  streak?: string
  highestRating?: string
}

export interface ViewedProfile {
  id: string
  alias: string
  country?: string
  profileId: string
  isPrimary: boolean
}

export type ProfileSummaryStatus = 'default' | 'loading' | 'stale' | 'error' | 'empty'

export interface ProfileSummaryProps {
  variant?: ProfileSummaryVariant
  /** The switcher is populated only from the authenticated `/api/me` payload — unauthenticated, it
   * renders nothing at all, not a disabled trigger (FR-045). */
  authenticated: boolean
  viewedProfile?: ViewedProfile
  linkedProfiles?: LinkedProfileOption[]
  entries: RatingEntryData[]
  status?: ProfileSummaryStatus
  freshnessLine?: ReactNode
  primaryChangeInFlight?: boolean
  unlinkInFlight?: boolean
  manageError?: ReactNode
  onSelectProfile?: (id: string) => void
  onMakePrimary?: (id: string) => void
  onLinkAnotherAccount?: () => void
  onUnlink?: () => void
  onBackToPrimary?: () => void
  onRetry?: () => void
  className?: string
}

/** Leaderboards the profile has never played are absent, not present-and-empty (FR-008). One DOM
 * layout only: a real `<table>` from `lg` up, stacked cards below it — never both, per the
 * "duplicated content breaks screen-reader output" rule (spec §8). */
export function ProfileSummary({
  variant = 'board',
  authenticated,
  viewedProfile,
  linkedProfiles = [],
  entries,
  status = 'default',
  freshnessLine,
  primaryChangeInFlight = false,
  unlinkInFlight = false,
  manageError,
  onSelectProfile,
  onMakePrimary,
  onLinkAnotherAccount,
  onUnlink,
  onBackToPrimary,
  onRetry,
  className,
}: ProfileSummaryProps) {
  const isTable = useBreakpoint('lg')
  const compact = variant === 'compact'

  const switcherItems: MenuItem[] = linkedProfiles.map((profile) => ({
    id: profile.id,
    label: profile.alias,
    checked: viewedProfile?.id === profile.id,
    badge: profile.isPrimary ? <Badge variant="accent">Primary</Badge> : undefined,
    disabled: primaryChangeInFlight,
    onSelect: () => onSelectProfile?.(profile.id),
  }))

  const manageItems: MenuItem[] = viewedProfile
    ? [
        ...(viewedProfile.isPrimary
          ? []
          : [
              {
                id: 'make-primary',
                label: 'Make primary',
                loading: primaryChangeInFlight,
                disabled: primaryChangeInFlight,
                onSelect: () => onMakePrimary?.(viewedProfile.id),
              },
            ]),
        {
          id: 'unlink',
          label: 'Unlink this profile',
          loading: unlinkInFlight,
          disabled: unlinkInFlight,
          onSelect: onUnlink,
        },
      ]
    : []

  return (
    <section
      aria-labelledby="profile-summary-alias"
      className={cx('bg-background p-4 md:p-6', className)}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            {authenticated && viewedProfile && (
              <Menu
                variant="selection"
                triggerLabel={
                  <>
                    <span id="profile-summary-alias" className="font-sans text-xl font-semibold">
                      {viewedProfile.alias}
                    </span>
                    <span aria-hidden="true">▾</span>
                  </>
                }
                triggerAriaLabel={`${viewedProfile.alias}, switch profile`}
                items={switcherItems}
                footerItem={{
                  id: 'link',
                  label: 'Link another Steam account',
                  onSelect: onLinkAnotherAccount,
                }}
              />
            )}
            {!authenticated && viewedProfile && (
              <span
                id="profile-summary-alias"
                className="font-sans text-xl font-semibold text-text-primary"
              >
                {viewedProfile.alias}
              </span>
            )}
            {!viewedProfile && (
              <span id="profile-summary-alias">
                <Skeleton variant="text" lines={1} className="w-32" />
              </span>
            )}
            {viewedProfile?.country && (
              <span className="font-sans text-sm text-text-secondary">{viewedProfile.country}</span>
            )}
          </div>
          {viewedProfile && (
            <span className="font-mono text-xs text-text-secondary">{viewedProfile.profileId}</span>
          )}
        </div>

        {!compact && viewedProfile && (
          <div className="flex items-center gap-2">
            <Menu
              variant="actions"
              triggerLabel="Manage"
              items={manageItems}
              errorItemId={manageError ? 'unlink' : null}
              errorMessage={manageError}
            />
          </div>
        )}
      </div>

      {viewedProfile && !viewedProfile.isPrimary && (
        <div className="mt-4">
          <Callout
            tone="info"
            heading="You are viewing a non-primary profile"
            headingLevel={3}
            actions={
              <>
                <Button variant="primary" onClick={() => onMakePrimary?.(viewedProfile.id)}>
                  Make primary
                </Button>
                <Button variant="secondary" onClick={onBackToPrimary}>
                  Back to primary
                </Button>
              </>
            }
          >
            You are viewing a profile that is not your primary one.
          </Callout>
        </div>
      )}

      <div className="mt-6">
        <RatingBoard
          entries={entries}
          status={status}
          isTable={isTable}
          compact={compact}
          onRetry={onRetry}
        />
      </div>

      {status !== 'loading' && freshnessLine && (
        <p className="mt-4 font-sans text-xs text-text-secondary">{freshnessLine}</p>
      )}
    </section>
  )
}

function RatingBoard({
  entries,
  status,
  isTable,
  compact,
  onRetry,
}: {
  entries: RatingEntryData[]
  status: ProfileSummaryStatus
  isTable: boolean
  compact: boolean
  onRetry?: () => void
}) {
  if (status === 'loading') {
    return (
      <div className={cx('flex flex-col gap-4', compact && 'flex-row gap-6')}>
        {(entries.length > 0 ? entries : [0, 1, 2]).map((entry, index) => (
          <div
            key={typeof entry === 'object' ? entry.leaderboardId : index}
            className="flex flex-col gap-2"
          >
            <Skeleton variant="text" lines={1} className="w-24" />
            <Skeleton variant="number" className="h-9 w-20" />
          </div>
        ))}
      </div>
    )
  }

  if (status === 'error' && entries.length === 0) {
    return (
      <Callout
        tone="danger"
        heading="We could not load your ratings"
        actions={
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        }
      />
    )
  }

  if (entries.length === 0) {
    return (
      <Callout tone="info" heading="No ratings yet">
        No leaderboard has a rating for this profile yet. Ratings appear after your first ranked
        match.
      </Callout>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {status === 'stale' && (
        <Callout
          tone="warning"
          heading="These figures could not be refreshed"
          actions={
            <Button variant="primary" onClick={onRetry}>
              Try again
            </Button>
          }
        />
      )}

      {isTable ? (
        <RatingTable entries={entries} />
      ) : (
        <div className={cx('flex flex-col gap-4', compact && 'md:flex-row md:gap-6')}>
          {entries.map((entry) => (
            <RatingCard key={entry.leaderboardId} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}

function RatingCard({ entry }: { entry: RatingEntryData }) {
  return (
    <article
      aria-labelledby={`entry-${entry.leaderboardId}-heading`}
      className="rounded-lg border border-border p-4"
    >
      <h3
        id={`entry-${entry.leaderboardId}-heading`}
        className="font-sans text-sm font-normal tracking-wide text-text-secondary"
      >
        {entry.leaderboardName}
      </h3>
      <dl className="mt-1 flex flex-wrap items-baseline gap-x-5 gap-y-2">
        <StatValue variant="hero" label="Rating" value={entry.rating} delta={entry.ratingDelta} />
        <StatValue
          variant="compact"
          label="Rank"
          status={entry.rank ? 'default' : 'empty'}
          value={entry.rank}
          secondaryLine={entry.rank ? undefined : 'Not ranked yet'}
        />
        <StatValue variant="compact" label="Record" value={`${entry.wins} W · ${entry.losses} L`} />
        <StatValue variant="compact" label="Win rate" value={entry.winRate} />
        {entry.streak && <StatValue variant="compact" label="Streak" value={entry.streak} />}
        {entry.highestRating && (
          <StatValue variant="compact" label="Best" value={entry.highestRating} />
        )}
      </dl>
      <RecordBar wins={entry.wins} losses={entry.losses} />
    </article>
  )
}

function RecordBar({ wins, losses }: { wins: number; losses: number }) {
  const total = wins + losses
  const winPercent = total === 0 ? 0 : Math.round((wins / total) * 100)
  return (
    <div
      aria-hidden="true"
      className="mt-2 flex h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken"
    >
      <div className="h-full bg-success" style={{ width: `${winPercent}%` }} />
      <div className="h-full bg-danger" style={{ width: `${100 - winPercent}%` }} />
    </div>
  )
}

function RatingTable({ entries }: { entries: RatingEntryData[] }) {
  return (
    <table className="w-full border-collapse text-left font-sans text-sm">
      <caption className="sr-only">Ratings for this profile</caption>
      <thead>
        <tr className="border-b border-border">
          <th scope="col" className="py-3 pr-6 font-normal text-text-secondary">
            Leaderboard
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Rating
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Change
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Rank
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Record
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Win rate
          </th>
          <th scope="col" className="py-3 pr-6 text-right font-normal text-text-secondary">
            Streak
          </th>
          <th scope="col" className="py-3 text-right font-normal text-text-secondary">
            Best
          </th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.leaderboardId} className="border-b border-border">
            <th scope="row" className="py-3 pr-6 font-normal text-text-primary">
              {entry.leaderboardName}
            </th>
            <td className="py-3 pr-6 text-right font-mono font-semibold tracking-tight text-text-primary">
              {entry.rating}
            </td>
            <td className="py-3 pr-6 text-right font-mono text-sm">
              {entry.ratingDelta && (
                <span className={entry.ratingDelta.value >= 0 ? 'text-success' : 'text-danger'}>
                  {entry.ratingDelta.value >= 0 ? '+' : '−'}
                  {entry.ratingDelta.formatted ?? Math.abs(entry.ratingDelta.value)}
                </span>
              )}
            </td>
            <td className="py-3 pr-6 text-right font-mono text-text-primary">
              {entry.rank ?? <span className="text-text-secondary">— Not ranked yet</span>}
            </td>
            <td className="py-3 pr-6 text-right font-mono text-text-primary">
              {entry.wins} W · {entry.losses} L
            </td>
            <td className="py-3 pr-6 text-right font-mono text-text-primary">{entry.winRate}</td>
            <td className="py-3 pr-6 text-right font-mono text-text-primary">{entry.streak}</td>
            <td className="py-3 text-right font-mono text-text-secondary">{entry.highestRating}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
