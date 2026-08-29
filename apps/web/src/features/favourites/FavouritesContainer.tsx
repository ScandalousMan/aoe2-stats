import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { Callout, FavouritesList } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { buildSignInHref } from '../auth/returnLocation'
import { favouritesQueryOptions, removeFavourite } from './api'
import { toFavouriteEntries } from './mappers'

// Wires `FavouritesList` (T348, packages/design-system) to `GET`/`DELETE /api/favourites` (T346)
// — the same discipline every other container in this feature follows (`SearchContainer.tsx`,
// `PlayerProfileContainer.tsx`): every visual state lives in the component, this module owns the
// data and the handlers.
//
// **Unlike those containers, a `sign_in_required` response here does not force a navigation.**
// `FavouritesList`'s own signed-out state (favourites-list.md §5a) *is* "ask them to sign in and
// return them to where they were" (US5 scenario 5) — silently whisking the visitor to `/sign-in`
// would skip past the very state this component exists to show. Instead this container refreshes
// the session (`meQueryOptions`), which is what actually flips `authenticated` to `false` and
// reveals that state, with `signInHref` already carrying `/favourites` as the return place.

export function FavouritesContainer() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery(meQueryOptions)
  const authenticated = meQuery.data?.authenticated ?? false

  const favouritesQuery = useQuery(favouritesQueryOptions)

  const [removingProfileIds, setRemovingProfileIds] = useState<ReadonlySet<string>>(new Set())
  const [removeFailed, setRemoveFailed] = useState(false)

  async function handleRemove(profileId: string) {
    setRemoveFailed(false)
    setRemovingProfileIds((current) => new Set(current).add(profileId))
    try {
      await removeFavourite(Number(profileId))
      await queryClient.invalidateQueries({ queryKey: favouritesQueryOptions.queryKey })
    } catch (error) {
      if (isApiErrorCode(error, 'sign_in_required') || isApiErrorCode(error, 'not_authenticated')) {
        void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
      } else {
        setRemoveFailed(true)
      }
    } finally {
      setRemovingProfileIds((current) => {
        const next = new Set(current)
        next.delete(profileId)
        return next
      })
    }
  }

  const listQueryFailed =
    favouritesQuery.isError &&
    !isApiErrorCode(favouritesQuery.error, 'sign_in_required') &&
    !isApiErrorCode(favouritesQuery.error, 'not_authenticated')

  const entries = favouritesQuery.data
    ? toFavouriteEntries(favouritesQuery.data.favourites, removingProfileIds)
    : undefined

  return (
    <main className="min-h-svh bg-background">
      {removeFailed && (
        <div className="px-4 pt-4 md:px-6">
          <Callout tone="danger" heading="We could not update your favourites" headingLevel={3}>
            Try again.
          </Callout>
        </div>
      )}
      <div className="px-4 py-6 md:px-6">
        <FavouritesList
          authenticated={authenticated}
          signInHref={buildSignInHref('/favourites')}
          onNavigate={(href) => void navigate({ to: href })}
          loading={authenticated && favouritesQuery.isPending}
          error={listQueryFailed}
          entries={entries}
          onRemove={(profileId) => void handleRemove(profileId)}
          onRetry={() => void favouritesQuery.refetch()}
        />
      </div>
    </main>
  )
}
