import { createFileRoute, redirect } from '@tanstack/react-router'
import { takePendingReturnLocation } from '../features/auth/returnLocation'

interface IndexSearch {
  /** `GET /api/auth/steam/callback` (contracts/http-api.md) 302s here on every outcome, success
   * or failure, carrying `?error=<code>` only on failure (`apps/api/.../routers/auth.py`). */
  error?: string
}

function validateIndexSearch(search: Record<string, unknown>): IndexSearch {
  return { error: typeof search.error === 'string' ? search.error : undefined }
}

/**
 * US5 scenario 5, `features/auth/returnLocation.ts`: a real sign-in always lands here first
 * (`GET /api/auth/steam/callback`'s fixed `/` redirect) before this `beforeLoad` sends an
 * authenticated visitor on. `takePendingReturnLocation` is the one place that pending value is
 * ever read, so the ordinary "just signed in" visit (nothing pending) is unaffected and still
 * lands on `/dashboard`, exactly as before this feature.
 */
export function resolveAuthenticatedRedirectTarget(): string {
  return takePendingReturnLocation() ?? '/dashboard'
}

// The minimum route-tree registration `routes/sign-in.tsx` (T036) needs to be reachable at all:
// the callback always lands here, never on `/sign-in` directly, so an unauthenticated visitor —
// which is exactly what every one of the four failure outcomes leaves them as — is forwarded to
// the sign-in screen with the failure code intact. An authenticated visitor is sent on to
// `/dashboard` (T037, `routes/dashboard.tsx`) — or back to a pending return location (US5 scenario
// 5, above) — rather than rendered here: `beforeLoad` always redirects one way or the other, so
// `Index` below never actually paints.
export const Route = createFileRoute('/')({
  validateSearch: validateIndexSearch,
  beforeLoad: ({ context, search }) => {
    if (!context.session.authenticated) {
      throw redirect({ to: '/sign-in', search: { error: search.error } })
    }
    throw redirect({ to: resolveAuthenticatedRedirectTarget() })
  },
  component: Index,
})

function Index() {
  // Unreachable — see `beforeLoad` above. `createFileRoute` still requires a component.
  return null
}
