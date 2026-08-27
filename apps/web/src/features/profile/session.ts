import type { AuthenticatedSession } from '../../lib/api'

/**
 * `ArchivalControl`'s two-way state (archival-control.md §3), derived from `GET /api/me`'s
 * `archival_objected` (`lib/api.ts`'s `AuthenticatedSession`, T405/T406).
 *
 * `archival_objected` is already the state that is true *now* — `archival_objected_at IS NOT
 * NULL` (contracts/http-api.md) — so this is a direct mapping, not a three-way decision the way
 * `consentDecisionFromSession` used to derive one. There is no "unanswered" state left to tell
 * apart from either: a user who has never objected and a user who objected and later resumed
 * both read `archival_objected === false`, and `ArchivalControl` does not distinguish them either
 * (archival-control.md §3) — the data model records no timestamp for a resumption.
 */
export type ArchivalControlState = 'archiving' | 'objected'

export function archivalControlStateFromSession(
  session: AuthenticatedSession,
): ArchivalControlState {
  return session.archival_objected ? 'objected' : 'archiving'
}
