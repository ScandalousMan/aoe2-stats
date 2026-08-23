import { describe, expect, it } from 'vitest'
import { assertPlayerProfileResponse, PlayerProfileResponseShapeError } from './api'

// T037a's rule, applied here for `GET /api/players/{profile_id}`: a type that describes the wire
// is a comment the compiler cannot verify — this is the one place that actually looks at the
// response body.

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

function validProfile() {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    alias_observed_at: '2026-08-12T00:00:00Z',
    ratings: [validSnapshot()],
  }
}

describe('assertPlayerProfileResponse', () => {
  it('accepts a well-formed profile with ratings', () => {
    expect(() => assertPlayerProfileResponse(validProfile())).not.toThrow()
  })

  it('accepts a never-ranked profile — empty ratings, not an error (US1 scenario 5)', () => {
    expect(() => assertPlayerProfileResponse({ ...validProfile(), ratings: [] })).not.toThrow()
  })

  it('accepts a null alias_observed_at', () => {
    expect(() =>
      assertPlayerProfileResponse({ ...validProfile(), alias_observed_at: null }),
    ).not.toThrow()
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertPlayerProfileResponse(null)).toThrow(PlayerProfileResponseShapeError)
    expect(() => assertPlayerProfileResponse('nope')).toThrow(PlayerProfileResponseShapeError)
  })

  it('rejects a body missing "profile_id"', () => {
    const body = validProfile()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete body.profile_id
    expect(() => assertPlayerProfileResponse(body)).toThrow(PlayerProfileResponseShapeError)
  })

  it('rejects a body missing "ratings"', () => {
    const body = validProfile()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete body.ratings
    expect(() => assertPlayerProfileResponse(body)).toThrow(PlayerProfileResponseShapeError)
  })

  it('rejects a rating snapshot missing a required field', () => {
    const snapshot = validSnapshot()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete snapshot.leaderboard_id
    expect(() => assertPlayerProfileResponse({ ...validProfile(), ratings: [snapshot] })).toThrow(
      PlayerProfileResponseShapeError,
    )
  })

  it('rejects a rating snapshot with the wrong type for rank', () => {
    const snapshot = validSnapshot()
    // @ts-expect-error deliberately malformed for the assertion under test
    snapshot.rank = 'not a number'
    expect(() => assertPlayerProfileResponse({ ...validProfile(), ratings: [snapshot] })).toThrow(
      PlayerProfileResponseShapeError,
    )
  })
})
