import type { MeResponse } from '../../lib/api'

/**
 * `GET /api/me` (`apps/api/.../routers/auth.py`) answers `{"ingest_consent": bool, ...}` —
 * snake_case, hand-assembled like every other dict that router returns (see `api.ts`'s module
 * docstring in this directory). `lib/api.ts`'s `MeResponse` type instead declares
 * `ingestConsentGranted`, a field the running backend has never sent. That mismatch predates this
 * task, lives in a file outside T037's scope (`apps/web/src/routes/dashboard.tsx` and
 * `apps/web/src/features/profile/` only), and is reported alongside this change rather than fixed
 * here.
 *
 * This reads both the field the backend actually sends and the one `MeResponse` claims to, so the
 * dashboard's consent gating (FR-034) is correct against the real response today and keeps
 * working unmodified whichever shape `MeResponse` is eventually corrected to.
 */
export function readIngestConsent(session: MeResponse): boolean {
  if (!session.authenticated) return false
  const raw = session as unknown as { ingest_consent?: unknown; ingestConsentGranted?: unknown }
  return raw.ingest_consent === true || raw.ingestConsentGranted === true
}
