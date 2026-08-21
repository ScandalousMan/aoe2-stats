/**
 * `GET /api/auth/steam/start` (contracts/http-api.md) is a real 302 to Steam, never something
 * called through `apps/web/src/lib/api.ts`'s `fetch`-based client: OpenID needs the browser's own
 * navigation so the signed `steam_oauth_state` cookie `security.py` sets travels through the round
 * trip to Steam and back. `SignInScreen`'s "Continue with Steam" action is therefore a real page
 * navigation (`window.location.assign`), and this is the one place that builds the URL for it.
 *
 * `?link=1` is what `apps/api/.../routers/auth.py` reads to add a second Steam account to the
 * caller's existing session instead of replacing it (FR-007) — only meaningful for an
 * already-authenticated caller, which is `apps/web/src/routes/sign-in.tsx`'s job to gate before
 * this function is ever called with `true`.
 */
export function buildSteamStartUrl(linkMode: boolean): string {
  return linkMode ? '/api/auth/steam/start?link=1' : '/api/auth/steam/start'
}
