import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Button, Callout, FavouriteToggle, ProfileSummary } from 'design-system'
import type { ProfileSummaryStatus } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { buildSignInHref } from '../auth/returnLocation'
import { addFavourite, favouritesQueryOptions, removeFavourite } from '../favourites/api'
import { playerProfileQueryOptions } from './api'
import { formatAliasObservedAt } from './format'
import { toRatingEntries, toViewedProfile } from './mappers'

// Wires `ProfileSummary`'s `subject="other"` view (T321) to `GET /api/players/{profile_id}`
// (T319) — any profile this service has observed, reached from `PlayerResultRow`'s `href`
// (`features/search/mappers.ts`) or a direct link, never only the caller's own. Mirrors
// `DashboardContainer.tsx`'s discipline for its own profile: every visual state lives in
// `ProfileSummary`, this module owns the data.
//
// T349: `FavouriteToggle` (US5) is wired here too, into `ProfileSummary`'s own `favouriteToggle`
// slot (profile-summary.md §11.1 point 3) — the same "one component, no second presentation"
// discipline FR-008 states for the profile itself.

export interface PlayerProfileContainerProps {
  profileId: number
}

export function PlayerProfileContainer({ profileId }: PlayerProfileContainerProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
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

  // --- Favourite toggle (T349, FR-013) -----------------------------------------------------------
  //
  // `GET /api/favourites` is the only route that says whether *this* profile is one of the
  // caller's own (`contracts/http-api.md`'s Favourites table has no per-profile lookup) — fetched
  // here the same way `DashboardContainer.tsx` fetches `profilesQueryOptions` alongside its own
  // session query, never gated behind `authenticated` explicitly: a signed-out caller answers
  // `401 sign_in_required`, which simply leaves `favourited` at its safe default, `false`.
  const favouritesQuery = useQuery(favouritesQueryOptions)
  const favourited =
    favouritesQuery.data?.favourites.some((entry) => entry.profile_id === profileId) ?? false

  const [favouritePending, setFavouritePending] = useState(false)
  const [favouriteLimitReached, setFavouriteLimitReached] = useState(false)
  const [favouriteRequestFailed, setFavouriteRequestFailed] = useState(false)

  async function runFavouriteMutation(action: () => Promise<unknown>) {
    setFavouritePending(true)
    setFavouriteLimitReached(false)
    setFavouriteRequestFailed(false)
    try {
      await action()
      await queryClient.invalidateQueries({ queryKey: favouritesQueryOptions.queryKey })
    } catch (error) {
      if (isApiErrorCode(error, 'favourites_limit_reached')) {
        // FR-016's bound race (favourite-toggle.md §5, "error" case 1) is the only shape this
        // client can ever show it in: neither this `409` nor any other route carries the
        // configured `FAVOURITES_MAX_PER_USER` value back to a client (`contracts/http-api.md`),
        // so `atLimit` is never computed ahead of a click below — this is the one signal a bound
        // ever produces.
        setFavouriteLimitReached(true)
      } else if (
        isApiErrorCode(error, 'not_authenticated') ||
        isApiErrorCode(error, 'sign_in_required')
      ) {
        void navigate({ to: '/sign-in' })
      } else {
        setFavouriteRequestFailed(true)
      }
    } finally {
      setFavouritePending(false)
    }
  }

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

  // Absent — not disabled — until a real profile has resolved, the same "nothing to act on yet"
  // rule `View match history` below already follows; `ProfileSummary` itself never renders this
  // slot for `subject="self"` (profile-summary.md §11.1 point 3), so no further guard is needed
  // here for a caller viewing their own profile through this route.
  const favouriteToggle = profile ? (
    <FavouriteToggle
      favourited={favourited}
      authenticated={session?.authenticated ?? false}
      loading={favouritePending}
      onAdd={() => void runFavouriteMutation(() => addFavourite(profileId))}
      onRemove={() => void runFavouriteMutation(() => removeFavourite(profileId))}
      signInHref={buildSignInHref(`/players/${profileId}`)}
      onNavigate={(href) => void navigate({ to: href })}
    />
  ) : undefined

  return (
    <main className="min-h-svh bg-background">
      {/* T383: `ProfileSummary`'s own "Back to search" (its `searchHref` below) renders only for
       * `status === 'not-found'`, where it collapses the whole component to one callout — a third
       * party's profile that *did* resolve had no way back to `/search` except the browser's own
       * back button. Suppressed for `not-found` itself so the two links do not double up.
       * `onClick` + `navigate()`, not `Button`'s `href`, for the same reason as
       * `DashboardContainer.tsx`'s new entry point: this is a SPA, and `href` renders a raw `<a>`
       * that forces a full document reload. */}
      {status !== 'not-found' && (
        <div className="flex justify-start px-4 pt-4 md:px-6">
          <Button variant="ghost" onClick={() => void navigate({ to: '/search' })}>
            Back to search
          </Button>
        </div>
      )}
      <ProfileSummary
        subject="other"
        authenticated={session?.authenticated ?? false}
        viewedProfile={profile ? toViewedProfile(profile) : undefined}
        entries={profile ? toRatingEntries(profile) : []}
        status={status}
        aliasObservedAtLabel={
          profile?.alias_observed_at ? formatAliasObservedAt(profile.alias_observed_at) : undefined
        }
        // `ProfileSummary`'s own default is `/search` too (T388 fixed the stale `/players`
        // placeholder) — kept explicit here so this container never silently drifts from it again.
        // Reached only from its `not-found` callout now that the general case has its own link
        // above.
        searchHref="/search"
        favouriteToggle={favouriteToggle}
        onRetry={() => void profileQuery.refetch()}
      />

      {/* favourite-toggle.md §5, "error" — the consuming layout's own error slot, beside the
       * control rather than inside it (that spec's own §2), the same convention
       * `DashboardContainer.tsx` follows for `makePrimaryError`. */}
      {favouriteLimitReached && (
        <div className="px-4 md:px-6">
          <Callout tone="warning" heading="You have reached your favourites limit" headingLevel={3}>
            Remove one to add another.
          </Callout>
        </div>
      )}
      {favouriteRequestFailed && (
        <div className="px-4 md:px-6">
          <Callout tone="danger" heading="We could not update your favourites" headingLevel={3}>
            Try again.
          </Callout>
        </div>
      )}

      {/* T331: the one link into `players.$profileId.matches.tsx` — without it the history route
       * is reachable only by typing the URL. Shown once a real profile has resolved; nothing to
       * link to yet while loading, and `not-found`'s own callout already owns the page below it. */}
      {profile && (
        <div className="flex justify-start px-4 pb-8 md:px-6">
          <Button
            variant="secondary"
            onClick={() =>
              void navigate({
                to: '/players/$profileId/matches',
                params: { profileId: String(profileId) },
              })
            }
          >
            View match history
          </Button>
        </div>
      )}
    </main>
  )
}
