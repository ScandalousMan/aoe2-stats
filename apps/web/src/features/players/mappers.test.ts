import { describe, expect, it } from 'vitest'
import type { ApiPlayerProfile, ApiPlayerRatingSnapshot } from './api'
import { toRatingEntries, toViewedProfile } from './mappers'

function snapshot(overrides: Partial<ApiPlayerRatingSnapshot> = {}): ApiPlayerRatingSnapshot {
  return {
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    rating: 1842,
    rank: 214,
    wins: 142,
    losses: 118,
    streak: 3,
    highest_rating: 1901,
    captured_at: '2026-08-22T10:00:00Z',
    ...overrides,
  }
}

function profile(overrides: Partial<ApiPlayerProfile> = {}): ApiPlayerProfile {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    alias_observed_at: '2026-08-12T00:00:00Z',
    ratings: [snapshot()],
    ...overrides,
  }
}

describe('toViewedProfile', () => {
  it('maps profile_id to a string id and profileId', () => {
    const result = toViewedProfile(profile({ profile_id: 42 }))
    expect(result.id).toBe('42')
    expect(result.profileId).toBe('42')
  })

  it('carries alias and country through', () => {
    const result = toViewedProfile(profile({ alias: 'Hera', country: 'Israel' }))
    expect(result.alias).toBe('Hera')
    expect(result.country).toBe('Israel')
  })

  it('maps a null country to undefined, never the literal null', () => {
    expect(toViewedProfile(profile({ country: null })).country).toBeUndefined()
  })

  it("is never primary — a third party is never the caller's own profile", () => {
    expect(toViewedProfile(profile()).isPrimary).toBe(false)
  })
})

describe('toRatingEntries', () => {
  it('maps an empty ratings list to an empty entries list (US1 scenario 5)', () => {
    expect(toRatingEntries(profile({ ratings: [] }))).toEqual([])
  })

  it('formats rating with thousands separators', () => {
    const result = toRatingEntries(profile({ ratings: [snapshot({ rating: 1842 })] }))
    expect(result[0]?.rating).toBe('1,842')
  })

  it('omits rank for a not-yet-ranked snapshot (rank <= 0)', () => {
    const result = toRatingEntries(profile({ ratings: [snapshot({ rank: -1 })] }))
    expect(result[0]?.rank).toBeUndefined()
  })

  it('carries wins and losses through as numbers', () => {
    const result = toRatingEntries(profile({ ratings: [snapshot({ wins: 10, losses: 5 })] }))
    expect(result[0]?.wins).toBe(10)
    expect(result[0]?.losses).toBe(5)
  })

  it('sorts by the shared leaderboard display order (1v1 RM before team RM)', () => {
    const result = toRatingEntries(
      profile({
        ratings: [
          snapshot({ leaderboard_id: 4, leaderboard_name: 'Team Random Map' }),
          snapshot({ leaderboard_id: 3, leaderboard_name: '1v1 Random Map' }),
        ],
      }),
    )
    expect(result.map((entry) => entry.leaderboardId)).toEqual(['3', '4'])
  })

  it('omits highestRating when the API sends null', () => {
    const result = toRatingEntries(profile({ ratings: [snapshot({ highest_rating: null })] }))
    expect(result[0]?.highestRating).toBeUndefined()
  })

  it('never carries a ratingDelta — there is nothing to diff against on this route', () => {
    const result = toRatingEntries(profile())
    expect(result[0]?.ratingDelta).toBeUndefined()
  })
})
