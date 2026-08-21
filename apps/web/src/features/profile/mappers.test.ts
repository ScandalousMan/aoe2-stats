import { describe, expect, it } from 'vitest'
import type { ApiProfile } from './api'
import {
  latestCapturedAt,
  toLinkedProfileOptions,
  toRatingEntries,
  toViewedProfile,
} from './mappers'

function profile(overrides: Partial<ApiProfile> = {}): ApiProfile {
  return {
    profile_id: 1,
    alias: 'ArchonQueen',
    country: 'FR',
    is_primary: true,
    linked_at: '2026-08-01T00:00:00Z',
    ratings: [],
    ...overrides,
  }
}

describe('toLinkedProfileOptions', () => {
  it('maps profile_id to a string id and passes alias and isPrimary through', () => {
    const result = toLinkedProfileOptions([
      profile({ profile_id: 7, alias: 'Someone', is_primary: false }),
    ])
    expect(result).toEqual([{ id: '7', alias: 'Someone', isPrimary: false }])
  })

  it('maps an empty list to an empty list', () => {
    expect(toLinkedProfileOptions([])).toEqual([])
  })
})

describe('toViewedProfile', () => {
  it('stringifies both id and profileId from the same numeric profile_id', () => {
    const result = toViewedProfile(profile({ profile_id: 42 }))
    expect(result.id).toBe('42')
    expect(result.profileId).toBe('42')
  })

  it('turns a null country into undefined, never the literal string "null"', () => {
    const result = toViewedProfile(profile({ country: null }))
    expect(result.country).toBeUndefined()
  })

  it('passes a real country code through unchanged', () => {
    const result = toViewedProfile(profile({ country: 'DE' }))
    expect(result.country).toBe('DE')
  })
})

describe('toRatingEntries', () => {
  it('maps snake_case API fields onto the camelCase entry shape', () => {
    const result = toRatingEntries(
      profile({
        ratings: [
          {
            leaderboard_id: 3,
            rating: 1500,
            rank: 250,
            wins: 10,
            losses: 5,
            streak: 2,
            highest_rating: 1600,
            captured_at: '2026-08-01T00:00:00Z',
          },
        ],
      }),
    )
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({
      leaderboardId: '3',
      leaderboardName: '1v1 Random Map',
      rating: '1,500',
      rank: '250',
      wins: 10,
      losses: 5,
      winRate: '67%',
      streak: 'W2',
      highestRating: '1,600',
    })
  })

  it('sorts entries by the leaderboard display order, not by array order', () => {
    const result = toRatingEntries(
      profile({
        ratings: [
          {
            leaderboard_id: 1,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
          {
            leaderboard_id: 3,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
          {
            leaderboard_id: 13,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
        ],
      }),
    )
    // DISPLAY_ORDER is [3, 4, 13, 14, 1, 2] — 1v1 Random Map, then 1v1 Empire Wars, then 1v1 DM.
    expect(result.map((entry) => entry.leaderboardId)).toEqual(['3', '13', '1'])
  })

  it('never computes a rating delta — this endpoint carries only the latest snapshot', () => {
    const result = toRatingEntries(
      profile({
        ratings: [
          {
            leaderboard_id: 3,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
        ],
      }),
    )
    expect(result[0].ratingDelta).toBeUndefined()
  })

  it('leaves highestRating undefined when the API reports null', () => {
    const result = toRatingEntries(
      profile({
        ratings: [
          {
            leaderboard_id: 3,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
        ],
      }),
    )
    expect(result[0].highestRating).toBeUndefined()
  })

  it('maps an empty ratings array to an empty entries array (never a fabricated one)', () => {
    expect(toRatingEntries(profile({ ratings: [] }))).toEqual([])
  })
})

describe('latestCapturedAt', () => {
  it('is undefined for a profile with no ratings yet', () => {
    expect(latestCapturedAt(profile({ ratings: [] }))).toBeUndefined()
  })

  it('picks the most recent captured_at across every leaderboard', () => {
    const result = latestCapturedAt(
      profile({
        ratings: [
          {
            leaderboard_id: 1,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-01T00:00:00Z',
          },
          {
            leaderboard_id: 3,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-15T00:00:00Z',
          },
          {
            leaderboard_id: 4,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-10T00:00:00Z',
          },
        ],
      }),
    )
    expect(result).toBe(new Date('2026-08-15T00:00:00Z').getTime())
  })

  it('ignores an unparsable captured_at rather than letting it win as NaN', () => {
    const result = latestCapturedAt(
      profile({
        ratings: [
          {
            leaderboard_id: 1,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: 'not-a-date',
          },
          {
            leaderboard_id: 3,
            rating: 1000,
            rank: null,
            wins: 0,
            losses: 0,
            streak: null,
            highest_rating: null,
            captured_at: '2026-08-10T00:00:00Z',
          },
        ],
      }),
    )
    expect(result).toBe(new Date('2026-08-10T00:00:00Z').getTime())
  })
})
