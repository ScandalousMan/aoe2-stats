import { describe, expect, it } from 'vitest'
import type { ApiMatchListRow, ApiOpponent } from './api'
import { toMatchRowData, toMatchRowDataList, toMatchRowOpponent } from './mappers'

function opponent(overrides: Partial<ApiOpponent> = {}): ApiOpponent {
  return { profile_id: 2, alias: 'Rival', civ_id: 3, ...overrides }
}

function row(overrides: Partial<ApiMatchListRow> = {}): ApiMatchListRow {
  return {
    game_id: 123,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    duration_seconds: 2040,
    civilisation: 7,
    result: 'win',
    rating_diff: 12,
    opponents: [opponent()],
    capture_status: 'stored',
    capture_deadline_at: null,
    ...overrides,
  }
}

describe('toMatchRowOpponent', () => {
  it('names the first opponent by alias, with no othersCount for a 1v1', () => {
    const result = toMatchRowOpponent([opponent({ alias: 'Rival' })])
    expect(result).toEqual({ alias: 'Rival', othersCount: undefined })
  })

  it('carries the remainder as othersCount for a team match', () => {
    const result = toMatchRowOpponent([
      opponent({ profile_id: 2, alias: 'First' }),
      opponent({ profile_id: 3, alias: 'Second' }),
      opponent({ profile_id: 4, alias: 'Third' }),
    ])
    expect(result).toEqual({ alias: 'First', othersCount: 2 })
  })

  it('never invents a bare count with no name', () => {
    const result = toMatchRowOpponent([])
    expect(result.alias).toBe('Unknown opponent')
    expect(result.othersCount).toBeUndefined()
  })

  it('falls back to a placeholder alias for a null opponent alias, never the literal null', () => {
    const result = toMatchRowOpponent([opponent({ alias: null })])
    expect(result.alias).toBe('Unknown opponent')
  })
})

describe('toMatchRowData', () => {
  it('maps game_id to a string gameId and builds the T076 detail href', () => {
    const result = toMatchRowData(row({ game_id: 456 }))
    expect(result.gameId).toBe('456')
    expect(result.href).toBe('/matches/456')
  })

  it('maps a win result to the "win" outcome', () => {
    expect(toMatchRowData(row({ result: 'win' })).outcome).toBe('win')
  })

  it('maps a loss result to the "loss" outcome', () => {
    expect(toMatchRowData(row({ result: 'loss' })).outcome).toBe('loss')
  })

  it('carries a positive rating_diff as a StatValueDelta', () => {
    const result = toMatchRowData(row({ rating_diff: 18 }))
    expect(result.ratingChange).toEqual({ value: 18, formatted: '18' })
  })

  it('carries a negative rating_diff with a positive formatted magnitude', () => {
    const result = toMatchRowData(row({ rating_diff: -9 }))
    expect(result.ratingChange).toEqual({ value: -9, formatted: '9' })
  })

  it('omits ratingChange entirely when there is nothing to report', () => {
    const result = toMatchRowData(row({ rating_diff: null }))
    expect(result.ratingChange).toBeUndefined()
  })

  it('falls back to "Unknown map" for a null map_name', () => {
    expect(toMatchRowData(row({ map_name: null })).map).toBe('Unknown map')
  })

  it("passes capture_status and capture_deadline_at through unmodified — the collapse is the badge's job", () => {
    const result = toMatchRowData(
      row({ capture_status: 'pending', capture_deadline_at: '2026-09-01T00:00:00Z' }),
    )
    expect(result.captureStatus).toBe('pending')
    expect(result.captureDeadlineAt).toBe('2026-09-01T00:00:00Z')
  })

  it('passes a null capture_status through as null, never a guessed default', () => {
    expect(toMatchRowData(row({ capture_status: null })).captureStatus).toBeNull()
  })
})

describe('toMatchRowDataList', () => {
  it('maps an empty list to an empty list', () => {
    expect(toMatchRowDataList([])).toEqual([])
  })

  it('maps every row in order', () => {
    const result = toMatchRowDataList([row({ game_id: 1 }), row({ game_id: 2 })])
    expect(result.map((r) => r.gameId)).toEqual(['1', '2'])
  })
})
