import { createFileRoute, redirect } from '@tanstack/react-router'
import { SearchContainer } from '../features/search/SearchContainer'

// T322: the player search route, `/search`. FR-001, FR-010 — disallowed in
// `apps/web/public/robots.txt` alongside `/players`, since a signed-in-only page that answers
// with any player's name is never publicly indexed (constitution IX).
export const Route = createFileRoute('/search')({
  beforeLoad: ({ context }) => {
    // Mirrors `dashboard.tsx`'s own gate: an unauthenticated visitor is sent to the screen built
    // for them rather than reaching a page whose every query needs a session.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: SearchRoute,
})

function SearchRoute() {
  return <SearchContainer />
}
