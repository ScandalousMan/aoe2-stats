import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiRequestError,
  ApiResponseShapeError,
  assertMeResponse,
  fetchMe,
  isApiErrorCode,
} from './api'

// T037a added `assertMeResponse` precisely because a type over a network payload is a comment
// the compiler cannot check — the old camelCase `MeResponse` fields (`profileId`, `isPrimary`,
// `ingestConsentGranted`) sat `undefined` for a whole phase with the compiler agreeing throughout.
// The point of this suite is the negative cases: proving the guard actually rejects a malformed
// or mismatched payload, not merely that it accepts a well-formed one.

function validAuthenticatedPayload() {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    ingest_consent: true,
    ingest_consent_at: '2026-08-01T00:00:00Z',
    ingest_consent_withdrawn_at: null as string | null,
    profiles: [
      { profile_id: 1, alias: 'ArchonQueen', country: 'FR' as string | null, is_primary: true },
    ],
  }
}

describe('assertMeResponse — accepts well-formed payloads', () => {
  it('accepts the documented unauthenticated shape', () => {
    expect(() => assertMeResponse({ authenticated: false })).not.toThrow()
  })

  it('accepts a well-formed authenticated payload with no linked profiles', () => {
    expect(() => assertMeResponse({ ...validAuthenticatedPayload(), profiles: [] })).not.toThrow()
  })

  it('accepts a well-formed authenticated payload with linked profiles', () => {
    expect(() => assertMeResponse(validAuthenticatedPayload())).not.toThrow()
  })

  it('accepts a null country on a linked profile', () => {
    const payload = validAuthenticatedPayload()
    payload.profiles[0].country = null
    expect(() => assertMeResponse(payload)).not.toThrow()
  })
})

describe('assertMeResponse — rejects malformed payloads', () => {
  it('rejects a payload that is not an object at all', () => {
    expect(() => assertMeResponse('not an object')).toThrow(ApiResponseShapeError)
    expect(() => assertMeResponse(null)).toThrow(ApiResponseShapeError)
    expect(() => assertMeResponse(undefined)).toThrow(ApiResponseShapeError)
  })

  it('rejects a payload missing "authenticated" entirely', () => {
    expect(() => assertMeResponse({})).toThrow(ApiResponseShapeError)
  })

  it('rejects "authenticated" as a truthy string instead of a boolean', () => {
    // This is exactly the shape a hand-rolled backend dict bug could produce — "true" the string
    // is truthy in every branch downstream that never checks `typeof`, which is the whole point
    // of asserting it here rather than trusting it.
    expect(() => assertMeResponse({ authenticated: 'true' })).toThrow(ApiResponseShapeError)
  })

  it('rejects a payload missing user_id when authenticated is true', () => {
    const payload = validAuthenticatedPayload() as Record<string, unknown>
    delete payload.user_id
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a non-boolean allowlisted', () => {
    const payload = { ...validAuthenticatedPayload(), allowlisted: 1 }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a non-boolean ingest_consent — the field the withdrawal defect turned on', () => {
    const payload = { ...validAuthenticatedPayload(), ingest_consent: 'yes' }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects ingest_consent_at that is neither a string nor null', () => {
    const payload = { ...validAuthenticatedPayload(), ingest_consent_at: 12345 }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects ingest_consent_withdrawn_at that is neither a string nor null', () => {
    const payload = { ...validAuthenticatedPayload(), ingest_consent_withdrawn_at: false }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a "profiles" field that is not an array', () => {
    const payload = { ...validAuthenticatedPayload(), profiles: {} }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a profile entry that is not an object', () => {
    const payload = { ...validAuthenticatedPayload(), profiles: ['not-an-object'] }
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a profile entry with a non-numeric profile_id', () => {
    const payload = validAuthenticatedPayload()
    ;(payload.profiles[0] as unknown as { profile_id: unknown }).profile_id = '1'
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a profile entry with a non-string alias', () => {
    const payload = validAuthenticatedPayload()
    ;(payload.profiles[0] as unknown as { alias: unknown }).alias = 42
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('rejects a profile entry with a non-boolean is_primary', () => {
    const payload = validAuthenticatedPayload()
    ;(payload.profiles[0] as unknown as { is_primary: unknown }).is_primary = 'true'
    expect(() => assertMeResponse(payload)).toThrow(ApiResponseShapeError)
  })

  it('would have rejected the old camelCase MeResponse shape this guard was built to catch', () => {
    // The exact defect T037a fixed: a plausible-looking payload using the wrong casing
    // convention entirely. Every camelCase field here is simply absent under the names this
    // module actually checks, so the guard must still fire.
    const camelCasePayload = {
      authenticated: true,
      userId: 'user-1',
      isAllowlisted: true,
      ingestConsentGranted: true,
      profiles: [{ profileId: 1, alias: 'ArchonQueen', isPrimary: true }],
    }
    expect(() => assertMeResponse(camelCasePayload)).toThrow(ApiResponseShapeError)
  })
})

describe('fetchMe', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves with the parsed body when the shape is valid', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: () => Promise.resolve({ authenticated: false }),
      }),
    )
    await expect(fetchMe()).resolves.toEqual({ authenticated: false })
  })

  it('throws ApiResponseShapeError, not a silently-substituted default, on a malformed body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: () => Promise.resolve({ authenticated: 'not-a-boolean' }),
      }),
    )
    await expect(fetchMe()).rejects.toBeInstanceOf(ApiResponseShapeError)
  })

  it('a shape error is not an ApiRequestError, so a caller cannot isApiErrorCode-match it away', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: () => Promise.resolve({ authenticated: 'not-a-boolean' }),
      }),
    )
    try {
      await fetchMe()
      throw new Error('expected fetchMe to throw')
    } catch (error) {
      expect(error).not.toBeInstanceOf(ApiRequestError)
      expect(isApiErrorCode(error, 'not_authenticated')).toBe(false)
    }
  })
})
