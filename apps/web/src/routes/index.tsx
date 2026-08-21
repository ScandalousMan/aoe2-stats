import { createFileRoute, redirect } from '@tanstack/react-router'

interface IndexSearch {
  /** `GET /api/auth/steam/callback` (contracts/http-api.md) 302s here on every outcome, success
   * or failure, carrying `?error=<code>` only on failure (`apps/api/.../routers/auth.py`). */
  error?: string
}

function validateIndexSearch(search: Record<string, unknown>): IndexSearch {
  return { error: typeof search.error === 'string' ? search.error : undefined }
}

// The minimum route-tree registration `routes/sign-in.tsx` (T036) needs to be reachable at all:
// the callback always lands here, never on `/sign-in` directly, so an unauthenticated visitor —
// which is exactly what every one of the four failure outcomes leaves them as — is forwarded to
// the sign-in screen with the failure code intact. T037 (dashboard) is what the authenticated
// branch below renders instead of this placeholder.
export const Route = createFileRoute('/')({
  validateSearch: validateIndexSearch,
  beforeLoad: ({ context, search }) => {
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in', search: { error: search.error } })
    }
  },
  component: Index,
})

function Index() {
  return (
    <main className="flex min-h-svh items-center justify-center">
      <p>aoe2-stats</p>
    </main>
  )
}
