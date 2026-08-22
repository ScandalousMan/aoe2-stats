import { createFileRoute, redirect } from '@tanstack/react-router'
import { MatchHistoryContainer } from '../features/matches/MatchHistoryContainer'

// T075: the match history route, `/matches`. Deliberately `matches.index.tsx` and never
// `matches.tsx` — under the flat file convention `@tanstack/router-cli` applies, `matches.tsx`
// beside T076's `matches.$gameId.tsx` would be that route's *parent layout* (its own generated
// `getParentRoute: () => MatchesRoute`, wrapped as `MatchesRouteWithChildren`), forcing the list to
// render an `<Outlet/>` for the detail to appear at all. `matches.index.tsx` instead — confirmed
// against the generated `routeTree.gen.ts`: `id: '/matches/'`, `path: '/matches'`, both hanging
// directly off the root — keeps `/matches` and `/matches/$gameId` as unrelated siblings, exactly
// as `dashboard.tsx` (T037) is unrelated to `sign-in.tsx` (T036).
export const Route = createFileRoute('/matches/')({
  beforeLoad: ({ context }) => {
    // Mirrors `dashboard.tsx`'s own gate: an unauthenticated visitor is sent to the screen built
    // for them rather than reaching a page whose every query needs a session.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: MatchHistoryRoute,
})

function MatchHistoryRoute() {
  return <MatchHistoryContainer />
}
