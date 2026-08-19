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
// router (T029) is authoritative once it exists; if its response ever disagrees with this type,
// fix the type here rather than adding a second shape further down the tree.

export interface SessionProfile {
  profileId: number
  alias: string
  isPrimary: boolean
}

export interface AuthenticatedSession {
  authenticated: true
  allowlisted: boolean
  ingestConsentGranted: boolean
  profiles: SessionProfile[]
}

export interface UnauthenticatedSession {
  authenticated: false
}

export type MeResponse = AuthenticatedSession | UnauthenticatedSession

export function fetchMe(): Promise<MeResponse> {
  return api.get<MeResponse>('/api/me')
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
