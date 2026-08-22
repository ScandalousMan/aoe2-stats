import { describe, expect, it } from 'vitest'
import { assertMatchesResponse, MatchesResponseShapeError } from './api'

// T037a's rule, applied here for `GET /api/matches`: a type that describes the wire is a comment
// the compiler cannot verify — this is the one place that actually looks at the response body.

function validRow() {
  return {
    game_id: 1,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
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

  it('rejects a non-string, non-null next_cursor', () => {
    expect(() => assertMatchesResponse({ matches: [], next_cursor: 42 })).toThrow(
      MatchesResponseShapeError,
    )
  })
})
