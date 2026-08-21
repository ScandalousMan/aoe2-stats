import type { SignInOutcome } from 'design-system'

// The set of outcome codes `SignInScreen` (T035, packages/design-system/specs/sign-in-screen.md)
// already has copy for. `contracts/http-api.md`'s Authentication failure-code table documents
// `steam_assertion_invalid`, `no_aoe2_profile`, `not_allowlisted` and `provider_unavailable`;
// `profile_already_linked` is FR-007's multi-account conflict, delivered the same way
// (`apps/api/.../routers/auth.py`, `_error_redirect`). `provider_unavailable` (T029b) is the
// backend's code for a Relic rate limit, a 5xx, a transport failure or a non-JSON body raised
// mid-callback; it maps onto the same `unreachable` outcome T034 built for a transport failure
// this front end could detect on its own (the `returning` phase's own 10s timeout, below) — the
// copy does not distinguish which side of the network failed, and neither outcome is the user's
// fault or something a retry cannot fix.
const knownOutcomeCodes: ReadonlySet<string> = new Set<SignInOutcome>([
  'no_aoe2_profile',
  'not_allowlisted',
  'steam_assertion_invalid',
  'unreachable',
  'profile_already_linked',
])

// `contracts/http-api.md`'s wire codes that are not themselves a `SignInOutcome` — `resolveOutcome`
// maps each one explicitly, per code, onto the outcome whose copy and baselines fit it, rather
// than leaning on the "anything unrecognised falls through to `unreachable`" rule below, which
// exists for a code this front end was never told about at all.
const outcomeAliases: Readonly<Record<string, SignInOutcome>> = {
  provider_unavailable: 'unreachable',
}

/**
 * Maps the `?error=` query parameter `GET /api/auth/steam/callback` redirects back with
 * (contracts/http-api.md) onto one of `SignInScreen`'s outcomes.
 *
 * `undefined` (no `error` parameter at all) is the ordinary first visit or a successful sign-in,
 * and maps to `null` — `OutcomeRegion` renders nothing (sign-in-screen.md §4, "empty").
 *
 * `provider_unavailable` (T029b) is looked up in `outcomeAliases` first and answers `unreachable`
 * — a documented mapping, not an accident of the fallback below.
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
  if (code in outcomeAliases) {
    return outcomeAliases[code]
  }
  return (knownOutcomeCodes.has(code) ? code : 'unreachable') as SignInOutcome
}
