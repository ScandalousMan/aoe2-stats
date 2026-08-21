import type { SignInOutcome } from 'design-system'

// The set of outcome codes `SignInScreen` (T035, packages/design-system/specs/sign-in-screen.md)
// already has copy for. `contracts/http-api.md`'s Authentication failure-code table documents
// `steam_assertion_invalid`, `no_aoe2_profile` and `not_allowlisted`; `profile_already_linked` is
// FR-007's multi-account conflict, delivered the same way (`apps/api/.../routers/auth.py`,
// `_error_redirect`). `unreachable` carries no backend code at all — T034 added it as the fourth
// outcome specifically because none of the other three cover a transport failure.
const knownOutcomeCodes: ReadonlySet<string> = new Set<SignInOutcome>([
  'no_aoe2_profile',
  'not_allowlisted',
  'steam_assertion_invalid',
  'unreachable',
  'profile_already_linked',
])

/**
 * Maps the `?error=` query parameter `GET /api/auth/steam/callback` redirects back with
 * (contracts/http-api.md) onto one of `SignInScreen`'s outcomes.
 *
 * `undefined` (no `error` parameter at all) is the ordinary first visit or a successful sign-in,
 * and maps to `null` — `OutcomeRegion` renders nothing (sign-in-screen.md §4, "empty").
 *
 * Any other value — including `not_authenticated` (the callback's own code for a link attempt
 * whose session expired mid-flow, not in the contract's documented table) and anything this
 * front end has not been told about yet — falls through to `unreachable`. That is deliberate and
 * not a guess at the right explanation: the rule this route is built to (T034, "no path ends on
 * an empty dashboard") does not admit a fifth case of "say nothing", so an error code nobody
 * anticipated still lands on a danger-toned callout with a retry rather than a blank panel.
 */
export function resolveOutcome(code: string | undefined): SignInOutcome | null {
  if (code === undefined) {
    return null
  }
  return (knownOutcomeCodes.has(code) ? code : 'unreachable') as SignInOutcome
}
