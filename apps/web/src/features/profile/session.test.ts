import { describe, expect, it } from 'vitest'
import type { AuthenticatedSession } from '../../lib/api'
import { archivalControlStateFromSession } from './session'

// `archivalControlStateFromSession` is the front-end half of T406/T407 (constitution IX 4.0.0):
// `GET /api/me` reports the state that is true *now* (`archival_objected_at IS NOT NULL`), and
// this is the one place that turns that single boolean into `ArchivalControl`'s `state` prop.
// There is no third "unanswered" case left to derive — the whole point of the amendment this
// module tracks is that a user who has never touched the switch is not a state distinct from one
// who touched it and resumed.

function session(overrides: Partial<AuthenticatedSession>): AuthenticatedSession {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    archival_objected: false,
    archival_objected_at: null,
    profiles: [],
    ...overrides,
  }
}

describe('archivalControlStateFromSession', () => {
  it('is "archiving" for a user who has never objected', () => {
    const result = archivalControlStateFromSession(
      session({ archival_objected: false, archival_objected_at: null }),
    )
    expect(result).toBe('archiving')
  })

  it('is "objected" when archival_objected is true, with its timestamp carried by the session', () => {
    const result = archivalControlStateFromSession(
      session({ archival_objected: true, archival_objected_at: '2026-08-10T00:00:00Z' }),
    )
    expect(result).toBe('objected')
  })

  it('is "archiving" again for a user who objected and later resumed — indistinguishable from never having objected', () => {
    // The exact shape a resumption leaves behind: `archival_objected` is false and
    // `archival_objected_at` is back to null, exactly as it is for a user who never touched the
    // switch at all. `archivalControlStateFromSession` must not invent a third state here.
    const result = archivalControlStateFromSession(
      session({ archival_objected: false, archival_objected_at: null }),
    )
    expect(result).toBe('archiving')
  })
})
