import { describe, expect, it } from 'vitest'
import {
  assertMatchDetailResponse,
  assertMatchesResponse,
  MatchDetailResponseShapeError,
  MatchesResponseShapeError,
} from './api'

// T037a's rule, applied here for `GET /api/matches`: a type that describes the wire is a comment
// the compiler cannot verify — this is the one place that actually looks at the response body.

function validRow() {
  return {
    game_id: 1,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    civilisation: 7,
    civilisation_name: 'Japanese',
    result: 'win',
    rating_diff: 12,
    opponents: [{ profile_id: 2, alias: 'Rival', civ_id: 3, civ_name: 'Celts' }],
    capture_status: 'stored',
    capture_deadline_at: null,
  }
}

describe('assertMatchesResponse', () => {
  it('accepts a well-formed page with matches and a null next_cursor', () => {
    expect(() => assertMatchesResponse({ matches: [validRow()], next_cursor: null })).not.toThrow()
  })

  it('accepts an opaque string next_cursor', () => {
    expect(() => assertMatchesResponse({ matches: [], next_cursor: 'b3BhcXVl' })).not.toThrow()
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertMatchesResponse(null)).toThrow(MatchesResponseShapeError)
    expect(() => assertMatchesResponse('nope')).toThrow(MatchesResponseShapeError)
  })

  it('rejects a body missing "matches"', () => {
    expect(() => assertMatchesResponse({ next_cursor: null })).toThrow(MatchesResponseShapeError)
  })

  it('rejects a row missing a required field', () => {
    const row = validRow()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete row.game_id
    expect(() => assertMatchesResponse({ matches: [row], next_cursor: null })).toThrow(
      MatchesResponseShapeError,
    )
  })

  it('rejects an opponent with the wrong shape', () => {
    const row = validRow()
    // @ts-expect-error deliberately malformed for the assertion under test
    row.opponents = [{ profile_id: 'not-a-number', alias: 'Rival', civ_id: 3 }]
    expect(() => assertMatchesResponse({ matches: [row], next_cursor: null })).toThrow(
      MatchesResponseShapeError,
    )
  })

  it('rejects a row with a non-string leaderboard_name (T070f)', () => {
    const row = validRow()
    // @ts-expect-error deliberately malformed for the assertion under test
    row.leaderboard_name = null
    expect(() => assertMatchesResponse({ matches: [row], next_cursor: null })).toThrow(
      MatchesResponseShapeError,
    )
  })

  it('rejects a non-string, non-null next_cursor', () => {
    expect(() => assertMatchesResponse({ matches: [], next_cursor: 42 })).toThrow(
      MatchesResponseShapeError,
    )
  })
})

// T076: `GET /api/matches/{game_id}`'s response shape (`api.ts`'s own `ApiMatchDetail`).

function validParticipant() {
  return {
    profile_id: 2,
    alias: 'Rival',
    team_id: 2,
    civ_id: 3,
    civ_name: 'Celts',
    color_id: 2,
    result: 'loss',
    rating: 1500,
    rating_diff: -12,
  }
}

function validDetail() {
  return {
    game_id: 700_800_900,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    patch: '101.101',
    participants: [validParticipant()],
    capture_status: 'stored',
    capture_deadline_at: '2026-09-12T10:34:00Z',
  }
}

describe('assertMatchDetailResponse', () => {
  it('accepts a well-formed match detail', () => {
    expect(() => assertMatchDetailResponse(validDetail())).not.toThrow()
  })

  it('accepts an empty participants array', () => {
    expect(() => assertMatchDetailResponse({ ...validDetail(), participants: [] })).not.toThrow()
  })

  it('accepts a null started_at', () => {
    expect(() => assertMatchDetailResponse({ ...validDetail(), started_at: null })).not.toThrow()
  })

  it('accepts a null patch (FR-018)', () => {
    expect(() => assertMatchDetailResponse({ ...validDetail(), patch: null })).not.toThrow()
  })

  it('rejects a non-string, non-null "patch"', () => {
    expect(() => assertMatchDetailResponse({ ...validDetail(), patch: 101 })).toThrow(
      MatchDetailResponseShapeError,
    )
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertMatchDetailResponse(null)).toThrow(MatchDetailResponseShapeError)
    expect(() => assertMatchDetailResponse('nope')).toThrow(MatchDetailResponseShapeError)
  })

  it('rejects a body missing "game_id"', () => {
    const body = validDetail()
    // @ts-expect-error deliberately malformed for the assertion under test
    delete body.game_id
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })

  it('rejects a body with a non-string "leaderboard_name" (T070f)', () => {
    const body = { ...validDetail(), leaderboard_name: null }
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })

  it('rejects a body whose "participants" is not an array', () => {
    expect(() => assertMatchDetailResponse({ ...validDetail(), participants: {} })).toThrow(
      MatchDetailResponseShapeError,
    )
  })

  it('rejects a participant with the wrong shape', () => {
    const body = validDetail()
    body.participants = [{ ...validParticipant(), profile_id: 'not-a-number' as unknown as number }]
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })

  it('rejects a participant with a non-nullable-number team_id', () => {
    const body = validDetail()
    body.participants = [{ ...validParticipant(), team_id: 'two' as unknown as number }]
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })

  it('accepts a null capture_status and capture_deadline_at (T070e: no capture row yet)', () => {
    expect(() =>
      assertMatchDetailResponse({
        ...validDetail(),
        capture_status: null,
        capture_deadline_at: null,
      }),
    ).not.toThrow()
  })

  it('rejects a non-string, non-null capture_status', () => {
    const body = { ...validDetail(), capture_status: 42 }
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })

  it('rejects a non-string, non-null capture_deadline_at', () => {
    const body = { ...validDetail(), capture_deadline_at: 42 }
    expect(() => assertMatchDetailResponse(body)).toThrow(MatchDetailResponseShapeError)
  })
})
