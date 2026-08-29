import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router'
import { SignInContainer } from '../features/auth/SignInContainer'
import { isSafeReturnPath } from '../features/auth/returnLocation'

export interface SignInSearch {
  /** `contracts/http-api.md`'s Authentication failure codes, echoed verbatim off
   * `GET /api/auth/steam/callback`'s redirect to `/` and forwarded here by `routes/index.tsx`'s
   * `beforeLoad`. `undefined` is the ordinary first visit or a successful sign-in. */
  error?: string
  /** Mirrors `?link=1` (contracts/http-api.md, FR-007): add a second Steam account instead of
   * replacing the session. Resolved to `true` only when the incoming value asks for linking (the
   * literal string `'1'` or `true`); left `undefined` otherwise, including when the parameter is
   * absent, so the router does not serialise it back onto the URL of an ordinary first visit. */
  link?: boolean
  /** US5 scenario 5, `favourite-toggle.md` §5a and `favourites-list.md` §5a: where to send the
   * caller back after a real sign-in — `features/auth/returnLocation.ts`'s
   * `buildSignInHref` is the one place that builds this URL. Left `undefined` for an ordinary
   * visit (no round trip pending) or an unsafe value, exactly `isSafeReturnPath`'s own check. */
  return?: string
}

export function validateSignInSearch(search: Record<string, unknown>): SignInSearch {
  return {
    error: typeof search.error === 'string' ? search.error : undefined,
    link: search.link === '1' || search.link === true ? true : undefined,
    return:
      typeof search.return === 'string' && isSafeReturnPath(search.return)
        ? search.return
        : undefined,
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
      returnTo={search.return}
      onNavigateHome={() => {
        void navigate({ to: '/' })
      }}
    />
  )
}
