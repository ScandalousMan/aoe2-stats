import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { ProfileSummary } from 'design-system'
import type { ProfileSummaryStatus } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { playerProfileQueryOptions } from './api'
import { formatAliasObservedAt } from './format'
import { toRatingEntries, toViewedProfile } from './mappers'

// Wires `ProfileSummary`'s `subject="other"` view (T321) to `GET /api/players/{profile_id}`
// (T319) — any profile this service has observed, reached from `PlayerResultRow`'s `href`
// (`features/search/mappers.ts`) or a direct link, never only the caller's own. Mirrors
// `DashboardContainer.tsx`'s discipline for its own profile: every visual state lives in
// `ProfileSummary`, this module owns the data.

export interface PlayerProfileContainerProps {
  profileId: number
}

export function PlayerProfileContainer({ profileId }: PlayerProfileContainerProps) {
  const navigate = useNavigate()
  const meQuery = useQuery(meQueryOptions)
  const session = meQuery.data

  // Mirrors `DashboardContainer.tsx`'s own effect: a cookie can expire while this page is
  // already open, so a live session check runs here too, not only the route's `beforeLoad` gate.
  useEffect(() => {
    if (session && !session.authenticated) {
      void navigate({ to: '/sign-in' })
    }
  }, [session, navigate])

  const profileQuery = useQuery(playerProfileQueryOptions(profileId))

  useEffect(() => {
    if (isApiErrorCode(profileQuery.error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
    }
  }, [profileQuery.error, navigate])

  // profile-summary.md §5 status derivation, generalised from `DashboardContainer.tsx`'s own for
  // a single query rather than two: `not-found` collapses the whole component to one callout
  // (US1 scenario: a searched player who has never been observed at all), which is exactly
  // `GET /api/players/{profile_id}`'s documented `404` (`routers/players.py`'s `_profile_not_found`).
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

  return (
    <main className="min-h-svh bg-background">
      <ProfileSummary
        subject="other"
        authenticated={session?.authenticated ?? false}
        viewedProfile={profile ? toViewedProfile(profile) : undefined}
        entries={profile ? toRatingEntries(profile) : []}
        status={status}
        aliasObservedAtLabel={
          profile?.alias_observed_at ? formatAliasObservedAt(profile.alias_observed_at) : undefined
        }
        // `ProfileSummary`'s own default points at `/players` (a placeholder written before this
        // task decided the real route) — `search.tsx` is the actual search route T322 wires, so
        // this container overrides it explicitly rather than letting the two silently disagree.
        searchHref="/search"
        onRetry={() => void profileQuery.refetch()}
      />
    </main>
  )
}
