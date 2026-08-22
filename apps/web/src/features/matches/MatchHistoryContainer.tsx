import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Button, Callout, MatchList, ProfileSummary } from 'design-system'
import type { MatchListStatus, ProfileSummaryStatus } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { profilesQueryOptions, setPrimaryProfile } from '../profile/api'
import { formatFreshness } from '../profile/format'
import {
  latestCapturedAt,
  toLinkedProfileOptions,
  toRatingEntries,
  toViewedProfile,
} from '../profile/mappers'
import { matchesQueryOptions } from './api'
import { toMatchRowDataList } from './mappers'

// Wires `MatchList` and `ProfileSummary/compact` (packages/design-system) to this feature's real
// effects, the same discipline `DashboardContainer.tsx` established for the dashboard. The page
// header is `ProfileSummary/compact` (match-history.md §1, §3: "page headers on match history and
// match detail"), so the profile-switching plumbing below is a deliberate, narrower echo of
// `DashboardContainer.tsx`'s own — narrower because `compact` hides the "Manage" menu entirely
// (`ProfileSummary`'s own `!compact && viewedProfile` gate), so unlink and consent, which live
// only behind that menu or below it on the dashboard, have no place here at all.

export function MatchHistoryContainer() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery(meQueryOptions)
  const profilesQuery = useQuery(profilesQueryOptions)
  const session = meQuery.data

  // Mirrors `DashboardContainer.tsx`'s own effect: a cookie can expire while this page is already
  // open, so every query below also watches for `not_authenticated` and lands here too.
  useEffect(() => {
    if (session && !session.authenticated) {
      void navigate({ to: '/sign-in' })
    }
  }, [session, navigate])

  function redirectIfSessionExpired(error: unknown): boolean {
    if (isApiErrorCode(error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
      return true
    }
    return false
  }

  const authenticated = session?.authenticated ?? false
  const profiles = profilesQuery.data?.profiles ?? []

  // FR-043: "viewing" is a session-level selection that writes nothing — same rule
  // `DashboardContainer.tsx` follows. Switching the viewed profile here also changes whose match
  // history `MatchList` below shows.
  const [viewedProfileId, setViewedProfileId] = useState<number | null>(null)
  const primaryProfile = profiles.find((profile) => profile.is_primary)
  const viewedProfile =
    profiles.find((profile) => profile.profile_id === viewedProfileId) ?? primaryProfile

  const [primaryChangeInFlight, setPrimaryChangeInFlight] = useState(false)
  const [makePrimaryError, setMakePrimaryError] = useState<string | null>(null)

  async function handleMakePrimary(id: string) {
    const profileId = Number(id)
    setPrimaryChangeInFlight(true)
    setMakePrimaryError(null)
    try {
      await setPrimaryProfile(profileId)
      setViewedProfileId(profileId)
      await queryClient.invalidateQueries({ queryKey: profilesQueryOptions.queryKey })
      void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setMakePrimaryError('We could not change your primary profile. Try again.')
      }
    } finally {
      setPrimaryChangeInFlight(false)
    }
  }

  // --- ProfileSummary status (profile-summary.md §5), identical derivation to
  // `DashboardContainer.tsx` ----------------------------------------------------------------------

  const profilesLoading = profilesQuery.isPending
  const profilesHaveData = profilesQuery.data !== undefined
  let profileSummaryStatus: ProfileSummaryStatus = 'default'
  if (profilesLoading) {
    profileSummaryStatus = 'loading'
  } else if (profilesQuery.isError) {
    profileSummaryStatus = profilesHaveData ? 'stale' : 'error'
  } else if (viewedProfile && viewedProfile.ratings.length === 0) {
    profileSummaryStatus = 'empty'
  }

  const showEmptyAccount = !profilesLoading && !profilesQuery.isError && profiles.length === 0

  // --- Match history (FR-010, FR-027) -------------------------------------------------------------
  //
  // First page only: match-history.md's own anatomy (§2), states (§5) and visual acceptance
  // criteria (§10) never mention a "load more" or paged affordance, unlike every other control
  // (`DownloadAction`, the switcher, retry) which they spell out explicitly — `api.ts`'s
  // `next_cursor` plumbing stays typed and ready, but no pagination control is invented here
  // ahead of a spec that would have named one.
  const profileIdForMatches = viewedProfile?.profile_id ?? 0
  const matchesQuery = useQuery(matchesQueryOptions(profileIdForMatches))

  useEffect(() => {
    if (isApiErrorCode(matchesQuery.error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
    }
  }, [matchesQuery.error, navigate])

  let matchListStatus: MatchListStatus = 'default'
  if (!viewedProfile || matchesQuery.isPending) {
    matchListStatus = 'loading'
  } else if (matchesQuery.isError) {
    matchListStatus = 'error'
  } else if ((matchesQuery.data?.matches.length ?? 0) === 0) {
    matchListStatus = 'empty'
  }

  const matchRows = matchesQuery.data ? toMatchRowDataList(matchesQuery.data.matches) : []

  return (
    <main className="min-h-svh bg-background">
      {showEmptyAccount ? (
        <div className="px-4 py-6 md:px-6">
          <Callout
            tone="info"
            heading="No Steam account is linked yet"
            actions={
              <Button
                variant="primary"
                onClick={() => void navigate({ to: '/sign-in', search: { link: true } })}
              >
                Link a Steam account
              </Button>
            }
          >
            Link a Steam account to see your match history.
          </Callout>
        </div>
      ) : (
        <>
          <ProfileSummary
            variant="compact"
            authenticated={authenticated}
            viewedProfile={viewedProfile ? toViewedProfile(viewedProfile) : undefined}
            linkedProfiles={toLinkedProfileOptions(profiles)}
            entries={viewedProfile ? toRatingEntries(viewedProfile) : []}
            status={profileSummaryStatus}
            freshnessLine={
              viewedProfile ? formatFreshness(latestCapturedAt(viewedProfile)) : undefined
            }
            primaryChangeInFlight={primaryChangeInFlight}
            onSelectProfile={(id) => setViewedProfileId(Number(id))}
            onMakePrimary={(id) => void handleMakePrimary(id)}
            onLinkAnotherAccount={() => void navigate({ to: '/sign-in', search: { link: true } })}
            onBackToPrimary={() => setViewedProfileId(primaryProfile?.profile_id ?? null)}
            onRetry={() => void profilesQuery.refetch()}
          />

          {makePrimaryError && (
            <div className="px-4 md:px-6">
              <Callout
                tone="danger"
                heading="We could not change your primary profile"
                headingLevel={3}
              >
                {makePrimaryError}
              </Callout>
            </div>
          )}

          {/* match-history.md §7: "Page header (ProfileSummary/compact) to match list — space-6". */}
          <div className="mt-6 px-4 pb-8 md:px-6">
            <MatchList
              status={matchListStatus}
              matches={matchRows}
              onRetry={() => void matchesQuery.refetch()}
            />
          </div>
        </>
      )}
    </main>
  )
}
