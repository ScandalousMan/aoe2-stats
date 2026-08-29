import { createFileRoute, redirect } from '@tanstack/react-router'
import { FavouritesContainer } from '../features/favourites/FavouritesContainer'

// T349: the favourites route, `/favourites` (FR-013, FR-014). FR-015: disallowed in
// `apps/web/public/robots.txt` alongside `/search` and `/players` — a signed-in-only page
// listing the players one particular user cares about is exactly the kind of per-user private
// data those two entries already cover, never publicly indexed (constitution IX).
export const Route = createFileRoute('/favourites')({
  beforeLoad: ({ context }) => {
    // Mirrors `search.tsx`'s and `players.$profileId.index.tsx`'s own gate: an unauthenticated
    // visitor is sent to the screen built for them rather than reaching a page whose every query
    // needs a session. A session that dies *after* this check has passed is
    // `FavouritesContainer`'s own concern (its own module docstring) — this gate only covers the
    // ordinary, unauthenticated first visit.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in', search: { return: '/favourites' } })
    }
  },
  component: FavouritesRoute,
})

function FavouritesRoute() {
  return <FavouritesContainer />
}
