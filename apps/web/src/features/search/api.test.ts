import { describe, expect, it } from 'vitest'
import { assertPlayerSearchResponse, PlayerSearchResponseShapeError } from './api'

// T037a's rule, applied here for `GET /api/players/search`: a type that describes the wire is a
// comment the compiler cannot verify — this is the one place that actually looks at the response
// body.

function validResult() {
  return {
    profile_id: 196240,
    alias: 'TheViper',
    country: 'Netherlands',
    games_played: 8213,
    clan: null,
  }
}

describe('assertPlayerSearchResponse', () => {
  it('accepts a well-formed, non-degraded response', () => {
    expect(() =>
      assertPlayerSearchResponse({ results: [validResult()], degraded: false, reason: null }),
    ).not.toThrow()
  })

  it('accepts the found-nothing shape — empty results, not degraded (FR-003)', () => {
    expect(() =>
      assertPlayerSearchResponse({ results: [], degraded: false, reason: null }),
    ).not.toThrow()
  })

  it('accepts the degraded shape with a reason and locally-known results (FR-004d)', () => {
    expect(() =>
      assertPlayerSearchResponse({
        results: [validResult()],
        degraded: true,
        reason: 'search_source_unavailable',
      }),
    ).not.toThrow()
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertPlayerSearchResponse(null)).toThrow(PlayerSearchResponseShapeError)
    expect(() => assertPlayerSearchResponse('nope')).toThrow(PlayerSearchResponseShapeError)
  })

  it('rejects a body missing "results"', () => {
    expect(() => assertPlayerSearchResponse({ degraded: false, reason: null })).toThrow(
      PlayerSearchResponseShapeError,
    )
  })

  it('rejects a body missing "degraded"', () => {
    expect(() => assertPlayerSearchResponse({ results: [], reason: null })).toThrow(
      PlayerSearchResponseShapeError,
    )
  })

  it('rejects a result missing a required field', () => {
    const result = validResult()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete result.profile_id
    expect(() =>
      assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
    ).toThrow(PlayerSearchResponseShapeError)
  })

  it('rejects a result with the wrong type for games_played', () => {
    const result = validResult()
    // @ts-expect-error deliberately malformed for the assertion under test
    result.games_played = 'a lot'
    expect(() =>
      assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
    ).toThrow(PlayerSearchResponseShapeError)
  })

  it('rejects a non-string, non-null reason', () => {
    expect(() => assertPlayerSearchResponse({ results: [], degraded: true, reason: 7 })).toThrow(
      PlayerSearchResponseShapeError,
    )
  })

  // `unverified_steam_id` (constitution IX 3.0.0, FR-004b) — optional today because T398 has not
  // wired it onto the wire yet (`ApiPlayerSearchResult`'s own docstring); still validated when
  // present, per T037a's rule.
  describe('unverified_steam_id', () => {
    it('accepts a result missing the key entirely, ahead of T398', () => {
      const result = validResult()
      expect(() =>
        assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
      ).not.toThrow()
    })

    it('accepts a result carrying the claim as a string', () => {
      const result = { ...validResult(), unverified_steam_id: '76561198012345678' }
      expect(() =>
        assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
      ).not.toThrow()
    })

    it("accepts a result carrying the claim as null (FR-004d's degraded fallback)", () => {
      const result = { ...validResult(), unverified_steam_id: null }
      expect(() =>
        assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
      ).not.toThrow()
    })

    it('rejects a result with the wrong type for unverified_steam_id', () => {
      const result = { ...validResult(), unverified_steam_id: 76561198 }
      expect(() =>
        assertPlayerSearchResponse({ results: [result], degraded: false, reason: null }),
      ).toThrow(PlayerSearchResponseShapeError)
    })
  })
})
