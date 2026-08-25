import { createFileRoute, redirect } from '@tanstack/react-router'
import { PlayerProfileContainer } from '../features/players/PlayerProfileContainer'

// T322: any player's profile, `/players/$profileId` — the route `PlayerResultRow`'s `href`
// (`features/search/mappers.ts`) always builds. FR-010: disallowed in
// `apps/web/public/robots.txt` alongside `/search`, since a third party's profile is reachable by
// a signed-in beta user but never publicly indexed (constitution IX, FR-008a property 2).
export const Route = createFileRoute('/players/$profileId')({
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
