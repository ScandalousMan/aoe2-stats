import { createFileRoute, redirect } from '@tanstack/react-router'
import { PlayerMatchHistoryContainer } from '../features/players/PlayerMatchHistoryContainer'

// T331: any player's match history, `/players/$profileId/matches`. Deliberately its own top-level
// file, never a child of `players.$profileId.tsx` (T322) — mirrors `matches.$gameId.tsx`'s own
// note on the flat file convention `@tanstack/router-cli` applies: a `players.$profileId.tsx`
// *directory-style* parent would force `players.$profileId.tsx` itself to render an `<Outlet/>`
// for this route to ever appear, which it does not. FR-008a property 2: disallowed in
// `apps/web/public/robots.txt` alongside `/players/*`, since a third party's history is reachable
// by a signed-in beta user but never publicly indexed (constitution IX).
export const Route = createFileRoute('/players/$profileId/matches')({
  beforeLoad: ({ context }) => {
    // Mirrors `players.$profileId.tsx`'s own gate: an unauthenticated visitor is sent to the
    // screen built for them rather than reaching a page whose every query needs a session.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: PlayerMatchHistoryRoute,
})

function PlayerMatchHistoryRoute() {
  const { profileId } = Route.useParams()
  return <PlayerMatchHistoryContainer profileId={Number(profileId)} />
}
