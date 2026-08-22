import { createFileRoute, redirect } from '@tanstack/react-router'
import { MatchDetailContainer } from '../features/replays/MatchDetailContainer'

// T076: the match detail route, `/matches/$gameId`. Deliberately its own top-level file, never a
// child of `matches.index.tsx` (T075) — see that route's own docstring for why `matches.tsx` is
// never created: under the flat file convention `@tanstack/router-cli` applies, a `matches.tsx`
// here would become this route's *parent layout* (its own `getParentRoute: () => MatchesRoute`,
// wrapped as `MatchesRouteWithChildren`), forcing `matches.index.tsx` to render an `<Outlet/>` for
// this detail to ever appear. Confirmed against the generated `routeTree.gen.ts`: `id:
// '/matches/$gameId'`, `path: '/$gameId'`, hanging directly off the root exactly as `/matches/`
// does — neither route knows about the other, exactly as `dashboard.tsx` and `sign-in.tsx` (T037,
// T036) do not know about each other.
export const Route = createFileRoute('/matches/$gameId')({
  beforeLoad: ({ context }) => {
    // Mirrors `matches.index.tsx`'s own gate (T075) and `dashboard.tsx`'s before it: an
    // unauthenticated visitor is sent to the screen built for them rather than reaching a page
    // whose every query needs a session.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: MatchDetailRoute,
})

function MatchDetailRoute() {
  const { gameId } = Route.useParams()
  return <MatchDetailContainer gameId={gameId} />
}
