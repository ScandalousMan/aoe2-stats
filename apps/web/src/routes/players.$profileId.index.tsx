import { createFileRoute, redirect } from '@tanstack/react-router'
import { PlayerProfileContainer } from '../features/players/PlayerProfileContainer'

// T322: any player's profile, `/players/$profileId` — the route `PlayerResultRow`'s `href`
// (`features/search/mappers.ts`) always builds. FR-010: disallowed in
// `apps/web/public/robots.txt` alongside `/search`, since a third party's profile is reachable by
// a signed-in beta user but never publicly indexed (constitution IX, FR-008a property 2).
//
// `players.$profileId.index.tsx`, not `players.$profileId.tsx` (T331, `matches.index.tsx`'s own
// docstring carries the identical reasoning): `players.$profileId.matches.tsx` (T331) now exists
// beside it, and under the flat file convention `@tanstack/router-cli` applies, a bare
// `players.$profileId.tsx` would become *that* route's parent layout (its own generated
// `getParentRoute: () => PlayersProfileIdRoute`, wrapped as `PlayersProfileIdRouteWithChildren`),
// forcing this page to render an `<Outlet/>` for the history route to ever appear at all.
// `.index.tsx` instead keeps `/players/$profileId` and `/players/$profileId/matches` as unrelated
// siblings hanging directly off the root, exactly as `/matches` and `/matches/$gameId` already do.
export const Route = createFileRoute('/players/$profileId/')({
  beforeLoad: ({ context }) => {
    // Mirrors `dashboard.tsx`'s own gate: an unauthenticated visitor is sent to the screen built
    // for them rather than reaching a page whose every query needs a session.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: PlayerProfileRoute,
})

function PlayerProfileRoute() {
  const { profileId } = Route.useParams()
  return <PlayerProfileContainer profileId={Number(profileId)} />
}
