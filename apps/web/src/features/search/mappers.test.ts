import { describe, expect, it } from 'vitest'
import type { ApiPlayerSearchResult } from './api'
import { toPlayerSearchResult, toPlayerSearchResults } from './mappers'

function result(overrides: Partial<ApiPlayerSearchResult> = {}): ApiPlayerSearchResult {
  return {
    profile_id: 196240,
    alias: 'TheViper',
    country: 'Netherlands',
    games_played: 8213,
    clan: null,
    ...overrides,
  }
}

describe('toPlayerSearchResult', () => {
  it('maps profile_id to a string profileId', () => {
    expect(toPlayerSearchResult(result({ profile_id: 42 })).profileId).toBe('42')
  })

  it('builds the T322 profile route as href', () => {
    expect(toPlayerSearchResult(result({ profile_id: 42 })).href).toBe('/players/42')
  })

  it('carries alias, clan, country and gamesPlayed through unmodified', () => {
    const mapped = toPlayerSearchResult(
      result({ alias: 'Hera', clan: 'GL', country: 'Israel', games_played: 5120 }),
    )
    expect(mapped.alias).toBe('Hera')
    expect(mapped.clan).toBe('GL')
    expect(mapped.country).toBe('Israel')
    expect(mapped.gamesPlayed).toBe(5120)
  })

  it('carries a null gamesPlayed through as null, never a fabricated 0 (FR-004d)', () => {
    expect(toPlayerSearchResult(result({ games_played: null })).gamesPlayed).toBeNull()
  })

  it('carries a null country and clan through as null', () => {
    const mapped = toPlayerSearchResult(result({ country: null, clan: null }))
    expect(mapped.country).toBeNull()
    expect(mapped.clan).toBeNull()
  })

  // §4a, FR-004b: the source's own claim is carried through, never dropped and never renamed to
  // something that could read as verified.
  describe('unverifiedSteamId (§4a)', () => {
    it('carries the claim through unmodified when present', () => {
      const mapped = toPlayerSearchResult(result({ unverified_steam_id: '76561198012345678' }))
      expect(mapped.unverifiedSteamId).toBe('76561198012345678')
    })

    it('maps a null claim to null', () => {
      const mapped = toPlayerSearchResult(result({ unverified_steam_id: null }))
      expect(mapped.unverifiedSteamId).toBeNull()
    })

    it('maps a missing claim (ahead of T398) to null, not undefined', () => {
      const wireResult = result()
      delete wireResult.unverified_steam_id
      expect(toPlayerSearchResult(wireResult).unverifiedSteamId).toBeNull()
    })
  })
})

describe('toPlayerSearchResults', () => {
  it('maps an empty list to an empty list', () => {
    expect(toPlayerSearchResults([])).toEqual([])
  })

  it('maps every result in order', () => {
    const mapped = toPlayerSearchResults([result({ profile_id: 1 }), result({ profile_id: 2 })])
    expect(mapped.map((r) => r.profileId)).toEqual(['1', '2'])
  })
})
