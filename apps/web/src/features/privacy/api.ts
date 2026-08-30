import { api } from '../../lib/api'

// `apps/api/.../routers/privacy.py` (T090, T091, T092) — `POST`/`GET /api/privacy/export/{id}`,
// `GET`/`POST /api/privacy/erase`, `POST /api/privacy/object` (`contracts/http-api.md`'s Privacy
// table). Every field name here is verbatim what those handlers put on the wire, snake_case, the
// same convention every other `api.ts` in this app follows (T037a). The mapping to
// `DataExportPanel`'s/`AccountErasurePanel`'s/`ThirdPartyObjectionForm`'s camelCase callback
// shapes happens once, in each container.
//
// `/api/privacy/archival-objection` is not repeated here: `features/profile/api.ts`'s
// `setArchivalObjection` is the one caller, and `privacy.tsx` reuses it directly rather than this
// module holding a second copy of the same wire call.

// --- POST /api/privacy/export, GET /api/privacy/export/{id} (T090, FR-036) --------------------

export interface StartExportResponse {
  id: string
  status: 'completed' | 'queued'
}

/** The job runs to completion inside the `POST` itself (router module docstring) — there is no
 * queue on this platform — but the response shape still carries `status` for a future
 * asynchronous implementation to change nothing about what a caller reads. */
export function startExport(): Promise<StartExportResponse> {
  return api.post<StartExportResponse>('/api/privacy/export')
}

export type ExportStatusResponse =
  { id: string; status: 'queued' } | { id: string; status: 'completed'; download_url: string }

/** Ownership on the job id follows the same `not_found` discipline every other route in this
 * feature uses (router module docstring): a missing job, someone else's job, or a job of a
 * different kind all answer the identical `404 not_found`. */
export function pollExport(jobId: string): Promise<ExportStatusResponse> {
  return api.get<ExportStatusResponse>(`/api/privacy/export/${jobId}`)
}

// --- GET /api/privacy/erase, POST /api/privacy/erase (T091, FR-037) ---------------------------

export interface ErasureConfirmationResponse {
  confirmation_token: string
}

/** Mints a short-lived confirmation token; changes nothing (router module docstring — "does
 * nothing else; no row is written"). */
export function requestErasureConfirmation(): Promise<ErasureConfirmationResponse> {
  return api.get<ErasureConfirmationResponse>('/api/privacy/erase')
}

export interface EraseAccountResponse {
  status: 'erased'
}

/** Irreversible. `ApiRequestError.status === 403` (`lib/api.ts`) is exactly the
 * `confirmation_token_invalid` case `AccountErasurePanel` re-mints and retries against (router's
 * `_erasure_confirmation_invalid`). */
export function eraseAccount(confirmationToken: string): Promise<EraseAccountResponse> {
  return api.post<EraseAccountResponse>('/api/privacy/erase', {
    confirmation_token: confirmationToken,
  })
}

// --- POST /api/privacy/object (T092, FR-039) — unauthenticated by design ----------------------

export interface ObjectionResponse {
  id: string
  status: 'recorded'
}

/** No session cookie is read or required (router module docstring: "the one unauthenticated
 * write in the system"). `ApiRequestError.status === 429` is the rate-limited case
 * `ThirdPartyObjectionForm` renders as its warning callout. */
export function objectToProcessing(profileId: number): Promise<ObjectionResponse> {
  return api.post<ObjectionResponse>('/api/privacy/object', { profile_id: profileId })
}
