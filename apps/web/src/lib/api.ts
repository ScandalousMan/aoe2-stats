import { queryOptions } from '@tanstack/react-query'

// The API client (T017). Every route under contracts/http-api.md is reached through the
// functions here, never through a bare `fetch` in a route or feature module: this is the one
// place that knows the error envelope's shape and the one place session cookies are attached.
//
// Same-origin only: production serves the API and the static bundle from the same host through
// the `/api/(.*)` rewrite (api/index.py, vercel.json), and the documented local flow is
// `vercel dev`, which emulates that rewrite (CLAUDE.md "Commands"). Paths below are therefore
// always relative, never an absolute URL built from an env var — there is no second origin to
// configure.

/**
 * The machine-readable codes contracts/http-api.md documents today. The union stays open
 * (`string & {}`) because later phases add routes with their own codes — `profile_already_linked`
 * from T029, upload rejections from T080 — and a client must not refuse to compile against a code
 * this file has not been amended to list yet. New codes get added here as they ship; nothing
 * downstream should invent a second list.
 */
export type ApiErrorCode =
  | 'steam_assertion_invalid'
  | 'no_aoe2_profile'
  | 'not_allowlisted'
  | 'profile_already_linked'
  | 'network_error'
  | 'unknown_error'
  | (string & {})

export interface ApiErrorPayload {
  code: ApiErrorCode
  message: string
  detail?: unknown
}

/**
 * Thrown for every non-2xx response and for a request that never reached the server. Callers
 * branch on `.code`, never on `.message` (contracts/http-api.md: "wording can change without
 * breaking a client") — `.message` exists only to be logged or, as a last resort, shown verbatim.
 */
export class ApiRequestError extends Error {
  readonly status: number
  readonly code: ApiErrorCode
  readonly detail?: unknown

  constructor(status: number, error: ApiErrorPayload, options?: ErrorOptions) {
    super(error.message, options)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = error.code
    this.detail = error.detail
  }
}

/** Narrows `error` to `ApiRequestError` carrying `code`, so a `catch` block never touches `.message`. */
export function isApiErrorCode(error: unknown, code: ApiErrorCode): error is ApiRequestError {
  return error instanceof ApiRequestError && error.code === code
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  body?: unknown
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const hasBody = options.body !== undefined

  let response: Response
  try {
    response = await fetch(path, {
      method: options.method ?? 'GET',
      // The session cookie is `HttpOnly` + `Secure` + `SameSite=Lax` (T028); same-origin requests
      // attach it without needing `include`, and `same-origin` is the explicit, auditable choice
      // rather than the implicit default.
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      },
      body: hasBody ? JSON.stringify(options.body) : undefined,
    })
  } catch (cause) {
    // A request that never reached the server (offline, DNS, CORS) is not one of the API's own
    // error codes, but the caller still needs one to branch on rather than a bare exception type.
    throw new ApiRequestError(
      0,
      { code: 'network_error', message: 'The request could not be sent.' },
      { cause },
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const envelope = payload as { error?: ApiErrorPayload } | null
    throw new ApiRequestError(
      response.status,
      envelope?.error ?? {
        code: 'unknown_error',
        message: response.statusText || 'Request failed',
      },
    )
  }

  return payload as T
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'POST', body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
}

// --- GET /api/me --------------------------------------------------------------------------
//
// Shape mirrors what contracts/http-api.md promises today: "Session, allowlist state, consent
// state, linked profiles, which is primary", plus the documented `{"authenticated": false}` when
// signed out — a 200, never a 401, because this is the bootstrap call every page makes and an
// error status for the ordinary signed-out case would make every client log noise. The auth
// router (`apps/api/.../routers/auth.py`) is authoritative once it exists; if its response ever
// disagrees with this type, fix the type here rather than adding a second shape further down the
// tree.
//
// T037a: this type used to declare camelCase fields (`profileId`, `isPrimary`,
// `ingestConsentGranted`) that `GET /api/me` has never actually sent — the router hand-assembles
// a plain `dict[str, Any]`, snake_case, the same convention `features/profile/api.ts` already
// documents for `profiles.py` and `privacy.py`. Every field below is instead verbatim what the
// router puts in the body, and `assertMeResponse` checks that at the boundary rather than trusting
// a type the compiler cannot verify against a network response — the exact gap that let the old
// camelCase fields sit unnoticed, always `undefined`, with the compiler agreeing throughout.

export interface SessionProfile {
  profile_id: number
  alias: string
  country: string | null
  is_primary: boolean
}

export interface AuthenticatedSession {
  authenticated: true
  user_id: string
  allowlisted: boolean
  // The state that is true *now* — `ingest_consent_at IS NOT NULL AND
  // ingest_consent_withdrawn_at IS NULL` (contracts/http-api.md) — never merely "was granted at
  // some point", which a withdrawal would otherwise leave indistinguishable from a live consent.
  ingest_consent: boolean
  ingest_consent_at: string | null
  ingest_consent_withdrawn_at: string | null
  profiles: SessionProfile[]
}

export interface UnauthenticatedSession {
  authenticated: false
}

export type MeResponse = AuthenticatedSession | UnauthenticatedSession

/** Thrown by `assertMeResponse` when `GET /api/me`'s body does not match the shape this module
 * declares — a network response the compiler can never check on its own, so this is the one
 * place that actually looks. Deliberately not an `ApiRequestError`: it is not one of the API's own
 * documented failure codes, and a caller must not be able to `isApiErrorCode`-match it away and
 * silently fall back to some default session state. */
export class ApiResponseShapeError extends Error {
  constructor(path: string, detail: string) {
    super(`Unexpected response shape from ${path}: ${detail}`)
    this.name = 'ApiResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function assertSessionProfile(value: unknown, index: number): asserts value is SessionProfile {
  if (typeof value !== 'object' || value === null) {
    throw new ApiResponseShapeError('/api/me', `profiles[${index}] was not an object`)
  }
  const profile = value as Record<string, unknown>
  if (typeof profile.profile_id !== 'number') {
    throw new ApiResponseShapeError('/api/me', `profiles[${index}].profile_id was not a number`)
  }
  if (typeof profile.alias !== 'string') {
    throw new ApiResponseShapeError('/api/me', `profiles[${index}].alias was not a string`)
  }
  if (!isNullableString(profile.country)) {
    throw new ApiResponseShapeError('/api/me', `profiles[${index}].country was not string|null`)
  }
  if (typeof profile.is_primary !== 'boolean') {
    throw new ApiResponseShapeError('/api/me', `profiles[${index}].is_primary was not a boolean`)
  }
}

/** Validates `payload` against `MeResponse` and narrows to it, or throws `ApiResponseShapeError`
 * — loudly, not a silently-substituted default — the moment the response disagrees with what
 * this module declares. `fetchMe` is the one caller; every consumer downstream of it (`__root.tsx`'s
 * `beforeLoad`, `DashboardContainer.tsx`) can then trust the type without re-checking it. */
export function assertMeResponse(payload: unknown): asserts payload is MeResponse {
  if (typeof payload !== 'object' || payload === null) {
    throw new ApiResponseShapeError('/api/me', 'response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (typeof body.authenticated !== 'boolean') {
    throw new ApiResponseShapeError('/api/me', '"authenticated" was not a boolean')
  }
  if (body.authenticated === false) {
    return
  }
  if (typeof body.user_id !== 'string') {
    throw new ApiResponseShapeError('/api/me', '"user_id" was not a string')
  }
  if (typeof body.allowlisted !== 'boolean') {
    throw new ApiResponseShapeError('/api/me', '"allowlisted" was not a boolean')
  }
  if (typeof body.ingest_consent !== 'boolean') {
    throw new ApiResponseShapeError('/api/me', '"ingest_consent" was not a boolean')
  }
  if (!isNullableString(body.ingest_consent_at)) {
    throw new ApiResponseShapeError('/api/me', '"ingest_consent_at" was not string|null')
  }
  if (!isNullableString(body.ingest_consent_withdrawn_at)) {
    throw new ApiResponseShapeError('/api/me', '"ingest_consent_withdrawn_at" was not string|null')
  }
  if (!Array.isArray(body.profiles)) {
    throw new ApiResponseShapeError('/api/me', '"profiles" was not an array')
  }
  body.profiles.forEach((profile, index) => assertSessionProfile(profile, index))
}

export async function fetchMe(): Promise<MeResponse> {
  const payload = await api.get<unknown>('/api/me')
  assertMeResponse(payload)
  return payload
}

/**
 * Consumed by the root route's `beforeLoad` (T017) so every route sees the session through
 * router context rather than re-querying it, and by T036/T037 to invalidate it after sign-in,
 * sign-out or a change in linked profiles.
 */
export const meQueryOptions = queryOptions({
  queryKey: ['session', 'me'] as const,
  queryFn: fetchMe,
  staleTime: 60_000,
})
