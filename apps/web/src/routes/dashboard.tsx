import { createFileRoute, redirect } from '@tanstack/react-router'
import { DashboardContainer } from '../features/profile/DashboardContainer'

// T037: ratings per leaderboard, the profile switcher (FR-043), the unlink confirmation and the
// consent step. `index.tsx` (T036) sends an authenticated visitor straight here instead of
// rendering its own placeholder; `DashboardContainer` (`features/profile/`) owns every real
// effect this route needs.
export const Route = createFileRoute('/dashboard')({
  beforeLoad: ({ context }) => {
    // Mirrors `sign-in.tsx`'s own gate in reverse: that route sends an authenticated,
    // non-linking visitor away from itself; this one sends an unauthenticated visitor away from
    // here, to the screen built for them.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: DashboardRoute,
})

function DashboardRoute() {
  return <DashboardContainer />
}
