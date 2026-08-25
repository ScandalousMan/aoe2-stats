import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { Button, MatchList, ProfileSummary } from 'design-system'
import type { MatchListStatus, ProfileSummaryStatus } from 'design-system'
import { toMatchRowDataList } from '../matches/mappers'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { playerMatchesQueryOptions, playerProfileQueryOptions } from './api'
import { formatAliasObservedAt } from './format'
import { toRatingEntries, toViewedProfile } from './mappers'

// T331: any player's match history, `/players/$profileId/matches` — wires `MatchList`'s
// `subject="other"` reading (match-history.md §11.3) to `GET /api/players/{profile_id}/matches`
// (T328), the same row shape `MatchHistoryContainer.tsx` (T075) already renders for the caller's
// own. `PlayerProfileContainer.tsx` (T322) is this route's closest sibling — same two-query shape
// (`meQueryOptions` for the session, `playerProfileQueryOptions` for the subject), same
// `ProfileSummary` `subject="other"` header — this container adds only the match list beneath it.

export interface PlayerMatchHistoryContainerProps {
  profileId: number
}

export function PlayerMatchHistoryContainer({ profileId }: PlayerMatchHistoryContainerProps) {
  const navigate = useNavigate()
  const meQuery = useQuery(meQueryOptions)
  const session = meQuery.data

  // Mirrors `PlayerProfileContainer.tsx`'s own effect: a cookie can expire while this page is
  // already open, so a live session check runs here too, not only the route's `beforeLoad` gate.
  useEffect(() => {
    if (session && !session.authenticated) {
      void navigate({ to: '/sign-in' })
    }
  }, [session, navigate])

  const profileQuery = useQuery(playerProfileQueryOptions(profileId))
  const matchesQuery = useQuery(playerMatchesQueryOptions(profileId))

  useEffect(() => {
    if (
      isApiErrorCode(profileQuery.error, 'not_authenticated') ||
      isApiErrorCode(matchesQuery.error, 'not_authenticated')
    ) {
      void navigate({ to: '/sign-in' })
    }
  }, [profileQuery.error, matchesQuery.error, navigate])

  // profile-summary.md §5 status derivation, identical to `PlayerProfileContainer.tsx`'s own:
  // `not-found` collapses `ProfileSummary` to one callout (US1: a profile_id never observed at
  // all), which is exactly `GET /api/players/{profile_id}/matches`'s own `404` cause too
  // (`routers/players.py`'s `_profile_not_found` — the same lookup both routes share).
  let status: ProfileSummaryStatus = 'default'
  if (profileQuery.isPending) {
    status = 'loading'
  } else if (isApiErrorCode(profileQuery.error, 'not_found')) {
    status = 'not-found'
  } else if (profileQuery.isError) {
    status = profileQuery.data !== undefined ? 'stale' : 'error'
  } else if (profileQuery.data && profileQuery.data.ratings.length === 0) {
    status = 'empty'
  }

  const profile = profileQuery.data
  const notFound = status === 'not-found'

  // match-history.md §11.3: `subjectAlias` is spliced into the list's caption and empty-state
  // sentence, so the list stays "loading" until the profile itself has resolved — never a row
  // with `undefined` standing in for the alias.
  let matchListStatus: MatchListStatus = 'default'
  if (!profile || matchesQuery.isPending) {
    matchListStatus = 'loading'
  } else if (matchesQuery.isError) {
    matchListStatus = 'error'
  } else if ((matchesQuery.data?.matches.length ?? 0) === 0) {
    matchListStatus = 'empty'
  }

  const matchRows = matchesQuery.data ? toMatchRowDataList(matchesQuery.data.matches) : []

  return (
    <main className="min-h-svh bg-background">
      {/* Mirrors `PlayerProfileContainer.tsx`'s T383 top-bar link: suppressed for `not-found`,
       * where `ProfileSummary`'s own "Back to search" already carries the round trip. */}
      {!notFound && (
        <div className="flex justify-start px-4 pt-4 md:px-6">
          <Button
            variant="ghost"
            onClick={() =>
              void navigate({ to: '/players/$profileId', params: { profileId: String(profileId) } })
            }
          >
            Back to profile
          </Button>
        </div>
      )}
      <ProfileSummary
        variant="compact"
        subject="other"
        authenticated={session?.authenticated ?? false}
        viewedProfile={profile ? toViewedProfile(profile) : undefined}
        entries={profile ? toRatingEntries(profile) : []}
        status={status}
        aliasObservedAtLabel={
          profile?.alias_observed_at ? formatAliasObservedAt(profile.alias_observed_at) : undefined
        }
        searchHref="/search"
        onRetry={() => void profileQuery.refetch()}
      />

      {/* match-history.md §7: page header to match list — `space-6`. */}
      {!notFound && (
        <div className="mt-6 px-4 pb-8 md:px-6">
          <MatchList
            status={matchListStatus}
            matches={matchRows}
            subject="other"
            subjectAlias={profile?.alias}
            onRetry={() => void matchesQuery.refetch()}
            onNavigate={(href) => void navigate({ to: href })}
          />
        </div>
      )}
    </main>
  )
}
