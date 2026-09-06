import { createFileRoute, redirect } from '@tanstack/react-router'
import { AnalysisContainer } from '../features/analysis/AnalysisContainer'
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
  return (
    // T372, US4 / T558: rendered as `MatchDetailContainer`'s own trailing child rather than a
    // route-level sibling, so the two share exactly one `Page` — one main landmark, one width and
    // padding, one between-sections rhythm — instead of `AnalysisContainer` re-deriving `Page`'s
    // own padding from outside it (`AnalysisContainer`'s own module docstring explains why it
    // stays a separate component: it shares `MatchDetailContainer`'s `GET /api/matches/{game_id}`
    // query key, one request either way). It renders nothing at all for a `gameId` this service
    // holds no match for, matching `MatchDetailContainer`'s own gate for `ReplayAvailabilityList`.
    <MatchDetailContainer gameId={gameId}>
      <AnalysisContainer gameId={gameId} />
    </MatchDetailContainer>
  )
}
