import { afterEach, describe, expect, it } from 'vitest'
import { savePendingReturnLocation } from '../features/auth/returnLocation'
import { resolveAuthenticatedRedirectTarget } from './index'

// US5 scenario 5: a real sign-in always lands on `/` first (`GET /api/auth/steam/callback`'s
// fixed redirect), so this is the one place that can send an authenticated visitor back to where
// they were instead of the ordinary `/dashboard` — `SignInContainer.test.tsx` proves the value is
// saved before the round trip; this proves it is read and consumed on the way back.

describe('resolveAuthenticatedRedirectTarget', () => {
  afterEach(() => {
    window.sessionStorage.clear()
  })

  it('falls back to /dashboard when nothing is pending — the ordinary sign-in', () => {
    expect(resolveAuthenticatedRedirectTarget()).toBe('/dashboard')
  })

  it('returns a pending return location and consumes it', () => {
    savePendingReturnLocation('/players/12345')

    expect(resolveAuthenticatedRedirectTarget()).toBe('/players/12345')
    // Consumed — a second authenticated visit (e.g. an unrelated later sign-in) does not replay
    // a stale destination from this one.
    expect(resolveAuthenticatedRedirectTarget()).toBe('/dashboard')
  })
})
