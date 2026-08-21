import { describe, expect, it } from 'vitest'
import { resolveOutcome } from './outcome'

// `resolveOutcome` maps `GET /api/auth/steam/callback`'s `?error=` code (contracts/http-api.md)
// onto one of `SignInScreen`'s outcomes. Three behaviours matter and each has its own defect
// class if it regresses: an undocumented code must never fall through silently (T034's "no path
// ends on an empty dashboard"), a documented-but-aliased code must land on the outcome its alias
// names rather than on the generic fallback, and the empty case (`undefined`) must stay `null`
// rather than painting an outcome nobody asked for.

describe('resolveOutcome', () => {
  it('maps undefined to null (ordinary first visit or a successful sign-in)', () => {
    expect(resolveOutcome(undefined)).toBeNull()
  })

  it.each([
    ['no_aoe2_profile', 'no_aoe2_profile'],
    ['not_allowlisted', 'not_allowlisted'],
    ['steam_assertion_invalid', 'steam_assertion_invalid'],
    ['unreachable', 'unreachable'],
    ['profile_already_linked', 'profile_already_linked'],
  ] as const)('passes the known code %s through unchanged', (code, expected) => {
    expect(resolveOutcome(code)).toBe(expected)
  })

  it('maps provider_unavailable (T029b) onto unreachable, not the generic fallback', () => {
    // This is a documented alias (contracts/http-api.md), not the "anything unrecognised" rule
    // below — asserting it here catches a regression that deletes the alias table and lets the
    // fallback quietly produce the same answer for the wrong reason.
    expect(resolveOutcome('provider_unavailable')).toBe('unreachable')
  })

  it('falls through to unreachable for a code this front end has never been told about', () => {
    expect(resolveOutcome('some_future_code_nobody_anticipated')).toBe('unreachable')
  })

  it('falls through to unreachable for not_authenticated (link attempt whose session expired)', () => {
    // Documented in the module docstring as deliberately not in the contract's failure table.
    expect(resolveOutcome('not_authenticated')).toBe('unreachable')
  })

  it('falls through to unreachable for an empty string', () => {
    expect(resolveOutcome('')).toBe('unreachable')
  })
})
