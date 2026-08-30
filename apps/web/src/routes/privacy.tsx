import { createFileRoute, redirect } from '@tanstack/react-router'
import { PrivacyContainer } from '../features/privacy/PrivacyContainer'

// T095: the signed-in data-rights route, `/privacy` — consent state (`ArchivalControl`), export
// request and download (`DataExportPanel`), and erasure with its confirmation
// (`AccountErasurePanel`). Disallowed in `apps/web/public/robots.txt` alongside `/favourites`:
// one user's own export and erasure controls, never publicly indexed.
export const Route = createFileRoute('/privacy')({
  beforeLoad: ({ context }) => {
    // Mirrors `dashboard.tsx`'s and `favourites.tsx`'s own gate: an unauthenticated visitor is
    // sent to the screen built for them rather than reaching a page whose every control needs a
    // session. A session that dies *after* this check has passed is `PrivacyContainer`'s own
    // concern, the same discipline `DashboardContainer.tsx` and `FavouritesContainer.tsx` follow.
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in', search: { return: '/privacy' } })
    }
  },
  component: PrivacyRoute,
})

function PrivacyRoute() {
  return <PrivacyContainer />
}
