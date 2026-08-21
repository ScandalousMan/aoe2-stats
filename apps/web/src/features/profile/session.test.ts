import { describe, expect, it } from 'vitest'
import type { AuthenticatedSession } from '../../lib/api'
import { consentDecisionFromSession } from './session'

// `consentDecisionFromSession` is the front-end half of the defect T037a called the serious
// one: `GET /api/me` reports the consent state that is true *now*
// (`ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL`), and this is the one
// place that turns those two fields into the three-way decision `ConsentStep` renders. Getting
// the withdrawn case wrong — reporting 'accepted' or 'unanswered' for a user who granted and then
// withdrew — is exactly the bug a reload used to reintroduce before T037a: nothing in the type
// system catches a boolean read backwards, only a test that exercises all three states does.

function session(overrides: Partial<AuthenticatedSession>): AuthenticatedSession {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    ingest_consent: false,
    ingest_consent_at: null,
    ingest_consent_withdrawn_at: null,
    profiles: [],
    ...overrides,
  }
}

describe('consentDecisionFromSession', () => {
  it('is "unanswered" when consent was never granted or declined', () => {
    const result = consentDecisionFromSession(
      session({ ingest_consent: false, ingest_consent_at: null }),
    )
    expect(result).toBe('unanswered')
  })

  it('is "accepted" when ingest_consent is true, regardless of the recorded timestamp', () => {
    const result = consentDecisionFromSession(
      session({
        ingest_consent: true,
        ingest_consent_at: '2026-08-01T00:00:00Z',
        ingest_consent_withdrawn_at: null,
      }),
    )
    expect(result).toBe('accepted')
  })

  it('is "declined" for a user who granted and then withdrew — the withdrawn case', () => {
    // The exact shape a withdrawal leaves behind: `ingest_consent` is now false, but
    // `ingest_consent_at` is not null (it was granted, once). This must read as "declined"
    // (the settings variant's "withdrawn" state), never "unanswered" — that would tell a user who
    // explicitly turned archival off that they have "not answered this yet".
    const result = consentDecisionFromSession(
      session({
        ingest_consent: false,
        ingest_consent_at: '2026-08-01T00:00:00Z',
        ingest_consent_withdrawn_at: '2026-08-10T00:00:00Z',
      }),
    )
    expect(result).toBe('declined')
  })

  it('is "declined" and not "unanswered" for a first-time explicit decline (no prior grant)', () => {
    // A user's very first answer can itself be "no" — `ingest_consent_at` records that decision
    // was made even though it did not grant anything, contracts/http-api.md.
    const result = consentDecisionFromSession(
      session({
        ingest_consent: false,
        ingest_consent_at: '2026-08-01T00:00:00Z',
        ingest_consent_withdrawn_at: null,
      }),
    )
    expect(result).toBe('declined')
  })

  it('ingest_consent true always wins over a stale withdrawn_at from a prior cycle', () => {
    // A user who withdrew and then granted again: `ingest_consent` is the source of truth for
    // "now", so a leftover `ingest_consent_withdrawn_at` from the earlier withdrawal must not
    // pull this back to "declined".
    const result = consentDecisionFromSession(
      session({
        ingest_consent: true,
        ingest_consent_at: '2026-08-15T00:00:00Z',
        ingest_consent_withdrawn_at: '2026-08-10T00:00:00Z',
      }),
    )
    expect(result).toBe('accepted')
  })
})
