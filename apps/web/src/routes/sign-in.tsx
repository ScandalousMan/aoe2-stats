import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router'
import { SignInContainer } from '../features/auth/SignInContainer'

export interface SignInSearch {
  /** `contracts/http-api.md`'s Authentication failure codes, echoed verbatim off
   * `GET /api/auth/steam/callback`'s redirect to `/` and forwarded here by `routes/index.tsx`'s
   * `beforeLoad`. `undefined` is the ordinary first visit or a successful sign-in. */
  error?: string
  /** Mirrors `?link=1` (contracts/http-api.md, FR-007): add a second Steam account instead of
   * replacing the session. Normalised to a boolean here so the rest of this route never compares
   * against the literal string `'1'` again. */
  link?: boolean
}

function validateSignInSearch(search: Record<string, unknown>): SignInSearch {
  return {
    error: typeof search.error === 'string' ? search.error : undefined,
    link: search.link === '1' || search.link === true,
  }
}

export const Route = createFileRoute('/sign-in')({
  validateSearch: validateSignInSearch,
  beforeLoad: ({ context, search }) => {
    // Linking a second Steam account only means something for an already-signed-in caller
    // (contracts/http-api.md, module docstring of `routers/auth.py`). A signed-in visitor who did
    // not ask to link one is sent home rather than shown a sign-in screen they no longer need —
    // T037 (dashboard) is what "home" renders for them.
    if (context.session.authenticated && !search.link) {
      throw redirect({ to: '/' })
    }
  },
  component: SignInRoute,
})

function SignInRoute() {
  const { session } = Route.useRouteContext()
  const search = Route.useSearch()
  const navigate = useNavigate()

  // `beforeLoad` above already sends an authenticated, non-linking visitor away — reached here,
  // `link` only takes effect when the session backing it is real, so a stale or guessed `?link=1`
  // on a signed-out visit degrades to an ordinary sign-in instead of a variant with a `Cancel`
  // button that has nowhere authenticated to cancel back to.
  const linkMode = search.link === true && session.authenticated

  return (
    <SignInContainer
      linkMode={linkMode}
      errorCode={search.error}
      onNavigateHome={() => {
        void navigate({ to: '/' })
      }}
    />
  )
}
