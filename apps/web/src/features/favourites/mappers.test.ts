import { describe, expect, it } from 'vitest'
import type { ApiFavouriteEntry } from './api'
import { toFavouriteEntries, toFavouriteEntryData } from './mappers'

function baseEntry(overrides: Partial<ApiFavouriteEntry> = {}): ApiFavouriteEntry {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    ratings: [
      {
        leaderboard_id: 3,
        leaderboard_name: '1v1 Random Map',
        rating: 1842,
        rank: 214,
        wins: 142,
        losses: 118,
        streak: 3,
        highest_rating: 1901,
        captured_at: '2026-08-22T10:00:00Z',
      },
    ],
    ...overrides,
  }
}

describe('toFavouriteEntryData', () => {
  it('maps identity, href and the primary ladder standing', () => {
    const data = toFavouriteEntryData(baseEntry())
    expect(data.profileId).toBe('87654321')
    expect(data.href).toBe('/players/87654321')
    expect(data.alias).toBe('rival_ace')
    expect(data.country).toBe('Germany')
    expect(data.standing).toEqual({
      label: '1v1 Random Map',
      value: '1,842',
      unit: 'Rank 214',
    })
  })

  it('picks the highest-priority ladder when several are played (favourites-list.md §4)', () => {
    const entry = baseEntry({
      ratings: [
        {
          leaderboard_id: 1, // Team Random Map — later in DISPLAY_ORDER
          leaderboard_name: 'Team Random Map',
          rating: 1500,
          rank: 90,
          wins: 10,
          losses: 5,
          streak: null,
          highest_rating: null,
          captured_at: '2026-08-22T10:00:00Z',
        },
        {
          leaderboard_id: 3, // 1v1 Random Map — first in DISPLAY_ORDER
          leaderboard_name: '1v1 Random Map',
          rating: 1842,
          rank: 214,
          wins: 142,
          losses: 118,
          streak: 3,
          highest_rating: 1901,
          captured_at: '2026-08-22T10:00:00Z',
        },
      ],
    })
    expect(toFavouriteEntryData(entry).standing.label).toBe('1v1 Random Map')
  })

  it('renders the empty StatValue state for a never-ranked favourite (US5 scenario 3)', () => {
    const data = toFavouriteEntryData(baseEntry({ ratings: [] }))
    expect(data.standing).toEqual({
      status: 'empty',
      label: 'Rating',
      secondaryLine: 'Not ranked yet',
    })
  })

  it("omits unit when the ladder has no rank yet (Relic's -1 convention)", () => {
    const entry = baseEntry()
    entry.ratings[0].rank = -1
    expect(toFavouriteEntryData(entry).standing.unit).toBeUndefined()
  })

  it('falls back to a placeholder alias when the profile has vanished (defensive nullable)', () => {
    const data = toFavouriteEntryData(baseEntry({ alias: null }))
    expect(data.alias).toBe('Player 87654321')
  })

  it('carries country through as null when unknown, never blank-filled', () => {
    const data = toFavouriteEntryData(baseEntry({ country: null }))
    expect(data.country).toBeNull()
  })

  it('sets removing from the loading-state options', () => {
    expect(toFavouriteEntryData(baseEntry(), { removing: true }).removing).toBe(true)
    expect(toFavouriteEntryData(baseEntry()).removing).toBeUndefined()
  })
})

describe('toFavouriteEntries', () => {
  it('maps a list and flags only the entries whose DELETE is in flight', () => {
    const entries = [baseEntry({ profile_id: 1 }), baseEntry({ profile_id: 2 })]
    const mapped = toFavouriteEntries(entries, new Set(['2']))
    expect(mapped.map((entry) => entry.removing)).toEqual([false, true])
  })
})
