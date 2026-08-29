// The return-to-place mechanism `favourite-toggle.md` §5a and `favourites-list.md` §5a require
// (US5 scenario 5: "asked to sign in and are returned to where they were") — carried through the
// one round trip nothing in this app can otherwise see across: `/sign-in`'s "Continue with Steam"
// is a full-page navigation (`SignInContainer.tsx`'s `continueWithSteam`, `steamStart.ts`'s own
// module docstring) that unloads this SPA entirely, and on success `GET /api/auth/steam/callback`
// always 302s to `/` (`apps/api/.../routers/auth.py`) — the app-side redirect target after a real
// sign-in is fixed server-side, and this feature does not touch `apps/api` to add one. No
// in-memory value survives that reload. `sessionStorage` is therefore the one place a return
// location can survive the round trip: written just before the navigation to Steam
// (`SignInContainer.tsx`), read once by `routes/index.tsx`'s `beforeLoad` on the way back, for
// exactly as long as this browser tab lives — a second tab, or a closed one, never sees it.

const STORAGE_KEY = 'aoe2stats:sign-in-return-to'

/**
 * Only a same-app, relative path is ever accepted — never a full URL, and never `//host` (a
 * protocol-relative address a browser resolves as an off-site redirect). Every value this module
 * carries comes from `window.location.pathname` (+ `search`) at a call site, or is replayed out
 * of `sessionStorage` later, and both are re-checked here rather than trusted once accepted.
 */
export function isSafeReturnPath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//')
}

/**
 * `FavouriteToggle.signInHref` / `FavouritesList.signInHref` (packages/design-system): the real
 * sign-in destination, carrying the caller's own location as `?return=` — `sign-in.tsx`'s
 * `validateSignInSearch` is the other half of this contract, and the query parameter name matches
 * it exactly.
 */
export function buildSignInHref(returnTo: string): string {
  return `/sign-in?return=${encodeURIComponent(returnTo)}`
}

/**
 * Written by `SignInContainer.tsx` immediately before the full-page navigation to Steam begins,
 * so the value survives the reload. An unsafe path is dropped rather than stored — the check
 * happens again on read (`takePendingReturnLocation`), but there is no reason to hold an invalid
 * value across the round trip either.
 */
export function savePendingReturnLocation(path: string): void {
  if (!isSafeReturnPath(path)) return
  window.sessionStorage.setItem(STORAGE_KEY, path)
}

/**
 * Consumes the pending return location, if any. A second read never sees the same value twice —
 * `routes/index.tsx`'s `beforeLoad` is the one caller, and an ordinary sign-in with nothing
 * pending must not be redirected somewhere stale from an earlier visit.
 */
export function takePendingReturnLocation(): string | null {
  const value = window.sessionStorage.getItem(STORAGE_KEY)
  if (value === null) return null
  window.sessionStorage.removeItem(STORAGE_KEY)
  return isSafeReturnPath(value) ? value : null
}
