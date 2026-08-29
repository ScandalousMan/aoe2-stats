import { describe, expect, it } from 'vitest'
import {
  assertFavouritesResponse,
  FavouriteMutationResponseShapeError,
  FavouritesResponseShapeError,
} from './api'

// T037a's rule, applied here for `GET /api/favourites`: a type that describes the wire is a
// comment the compiler cannot verify — this is the one place that actually looks at the response
// body. `FavouriteMutationResponseShapeError` (`PUT`/`DELETE`) is exercised through `addFavourite`
// and `removeFavourite` in `PlayerProfileContainer.test.tsx`, the same way `MatchDetailContainer`
// exercises the download route's own shape guard through its container rather than in isolation.

function validSnapshot() {
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
  }
}

function validEntry() {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    ratings: [validSnapshot()],
  }
}

describe('assertFavouritesResponse', () => {
  it('accepts a well-formed list', () => {
    expect(() => assertFavouritesResponse({ favourites: [validEntry()] })).not.toThrow()
  })

  it('accepts an empty list (FR-013: no favourites yet is not an error)', () => {
    expect(() => assertFavouritesResponse({ favourites: [] })).not.toThrow()
  })

  it('accepts a never-ranked favourite — empty ratings (US5 scenario 3)', () => {
    expect(() =>
      assertFavouritesResponse({ favourites: [{ ...validEntry(), ratings: [] }] }),
    ).not.toThrow()
  })

  it('accepts a null alias — the favourited profile has vanished (defensive nullable)', () => {
    expect(() =>
      assertFavouritesResponse({ favourites: [{ ...validEntry(), alias: null }] }),
    ).not.toThrow()
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertFavouritesResponse(null)).toThrow(FavouritesResponseShapeError)
    expect(() => assertFavouritesResponse('nope')).toThrow(FavouritesResponseShapeError)
  })

  it('rejects a body missing "favourites"', () => {
    expect(() => assertFavouritesResponse({})).toThrow(FavouritesResponseShapeError)
  })

  it('rejects an entry missing "profile_id"', () => {
    const entry = validEntry() as Record<string, unknown>
    delete entry.profile_id
    expect(() => assertFavouritesResponse({ favourites: [entry] })).toThrow(
      FavouritesResponseShapeError,
    )
  })

  it('rejects a rating snapshot with the wrong type for rank', () => {
    const snapshot = validSnapshot() as Record<string, unknown>
    snapshot.rank = 'not a number'
    expect(() =>
      assertFavouritesResponse({ favourites: [{ ...validEntry(), ratings: [snapshot] }] }),
    ).toThrow(FavouritesResponseShapeError)
  })
})

describe('FavouriteMutationResponseShapeError', () => {
  it('carries a message naming the offending field', () => {
    const error = new FavouriteMutationResponseShapeError('"favourited" was not a boolean')
    expect(error.message).toContain('favourited')
    expect(error.name).toBe('FavouriteMutationResponseShapeError')
  })
})
