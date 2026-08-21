import type { AuthenticatedSession } from '../../lib/api'

/**
 * `ConsentStep`'s three-way decision (consent-step.md §4.4), derived from `GET /api/me`'s
 * `ingest_consent` / `ingest_consent_at` (`lib/api.ts`'s `AuthenticatedSession`, T037a).
 *
 * `ingest_consent` is already the state that is true *now* — `ingest_consent_at IS NOT NULL AND
 * ingest_consent_withdrawn_at IS NULL` (contracts/http-api.md) — so `'accepted'` follows it
 * directly. A user who granted and then withdrew has `ingest_consent === false` but
 * `ingest_consent_at !== null`: that is `'declined'` (the settings variant, "withdrawn"), not
 * `'unanswered'`, which is reserved for a user who has never made either choice
 * (`ingest_consent_at === null`).
 *
 * T037a note: this file previously held `readIngestConsent`, a workaround for `GET /api/me`
 * never reporting a withdrawal (it read only "granted at least once", which a withdrawal cannot
 * be told apart from). Now that the router reports the state that is true right now, a reload no
 * longer needs a session-local override to show a withdrawal correctly — `DashboardContainer.tsx`
 * calls this directly on `session` instead.
 */
export type ConsentDecision = 'accepted' | 'declined' | 'unanswered'

export function consentDecisionFromSession(session: AuthenticatedSession): ConsentDecision {
  if (session.ingest_consent) return 'accepted'
  if (session.ingest_consent_at !== null) return 'declined'
  return 'unanswered'
}
