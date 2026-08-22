import { describe, expect, it } from 'vitest'
import type { ApiMatchDetail, ApiMatchListRow, ApiMatchParticipant, ApiOpponent } from './api'
import {
  toMatchDetailData,
  toMatchRowData,
  toMatchRowDataList,
  toMatchRowOpponent,
  toParticipantData,
  toTeamGroups,
} from './mappers'

function opponent(overrides: Partial<ApiOpponent> = {}): ApiOpponent {
  return { profile_id: 2, alias: 'Rival', civ_id: 3, civ_name: 'Celts', ...overrides }
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
    civilisation_name: 'Japanese',
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

  it('passes the server-named civilisation through (T070c), not the raw id', () => {
    expect(toMatchRowData(row({ civilisation_name: 'Turks' })).civilisation).toBe('Turks')
  })

  it('falls back to "Unknown civilisation" for a null civilisation_name', () => {
    expect(toMatchRowData(row({ civilisation_name: null })).civilisation).toBe(
      'Unknown civilisation',
    )
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

// --- T076: GET /api/matches/{game_id} -> MatchDetailPanel ---------------------------------------

function participant(overrides: Partial<ApiMatchParticipant> = {}): ApiMatchParticipant {
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
    ...overrides,
  }
}

function detail(overrides: Partial<ApiMatchDetail> = {}): ApiMatchDetail {
  return {
    game_id: 700_800_900,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    duration_seconds: 2040,
    participants: [
      participant({ profile_id: 1, team_id: 1, alias: 'Me', result: 'win', rating_diff: 12 }),
      participant({ profile_id: 2, team_id: 2, alias: 'Rival', result: 'loss', rating_diff: -12 }),
    ],
    capture_status: 'stored',
    capture_deadline_at: '2026-09-12T10:34:00Z',
    ...overrides,
  }
}

describe('toParticipantData', () => {
  it('maps profile_id to a string id', () => {
    expect(toParticipantData(participant({ profile_id: 42 })).id).toBe('42')
  })

  it('falls back to "Unknown player" for a null alias', () => {
    expect(toParticipantData(participant({ alias: null })).alias).toBe('Unknown player')
  })

  it('passes the server-named civilisation through (T070c)', () => {
    expect(toParticipantData(participant({ civ_name: 'Turks' })).civilisation).toBe('Turks')
  })

  it('maps a win result to the "win" outcome', () => {
    expect(toParticipantData(participant({ result: 'win' })).result).toBe('win')
  })

  it('falls back to "loss" for an unrecognised result, never letting it reach the component', () => {
    expect(toParticipantData(participant({ result: null })).result).toBe('loss')
  })

  it('carries a rating_diff as a StatValueDelta with a positive formatted magnitude', () => {
    expect(toParticipantData(participant({ rating_diff: -9 })).ratingChange).toEqual({
      value: -9,
      formatted: '9',
    })
  })

  it('omits ratingChange entirely when there is nothing to report', () => {
    expect(toParticipantData(participant({ rating_diff: null })).ratingChange).toBeUndefined()
  })
})

describe('toTeamGroups', () => {
  it('groups participants under the correct team, in the order each team is first seen', () => {
    const groups = toTeamGroups([
      participant({ profile_id: 1, team_id: 1 }),
      participant({ profile_id: 2, team_id: 2 }),
      participant({ profile_id: 3, team_id: 1 }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['team-1', 'team-2'])
    expect(groups[0]?.participants.map((p) => p.id)).toEqual(['1', '3'])
    expect(groups[1]?.participants.map((p) => p.id)).toEqual(['2'])
  })

  it('names each group "Team <n>"', () => {
    const groups = toTeamGroups([participant({ team_id: 4 })])
    expect(groups[0]?.name).toBe('Team 4')
  })

  it('drops no participant and duplicates none across a 2v2', () => {
    const participants = [
      participant({ profile_id: 1, team_id: 1 }),
      participant({ profile_id: 2, team_id: 1 }),
      participant({ profile_id: 3, team_id: 2 }),
      participant({ profile_id: 4, team_id: 2 }),
    ]
    const groups = toTeamGroups(participants)
    const allIds = groups.flatMap((group) => group.participants.map((p) => p.id))
    expect(allIds).toEqual(['1', '2', '3', '4'])
  })

  it('groups a null team_id into its own trailing group, never dropped or merged', () => {
    const groups = toTeamGroups([
      participant({ profile_id: 1, team_id: 1 }),
      participant({ profile_id: 2, team_id: null }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['team-1', 'team-none'])
    expect(groups[1]?.name).toBe('No team recorded')
    expect(groups[1]?.participants.map((p) => p.id)).toEqual(['2'])
  })

  it('maps an empty participant list to an empty team list', () => {
    expect(toTeamGroups([])).toEqual([])
  })
})

describe('toMatchDetailData', () => {
  it('maps game_id to a string gameId', () => {
    expect(toMatchDetailData(detail({ game_id: 123 })).gameId).toBe('123')
  })

  it('falls back to "Unknown map" for a null map_name', () => {
    expect(toMatchDetailData(detail({ map_name: null })).map).toBe('Unknown map')
  })

  it('formats the leaderboard id as a stand-in name (T076 — no server name for this field yet)', () => {
    expect(toMatchDetailData(detail({ leaderboard_id: 3 })).leaderboardName).toBe('Leaderboard 3')
  })

  it('formats duration in minutes', () => {
    expect(toMatchDetailData(detail({ duration_seconds: 2040 })).durationLabel).toBe('34 min')
  })

  it('prefers started_at for playedAtLabel when present', () => {
    const withStart = toMatchDetailData(
      detail({ started_at: '2026-08-22T10:00:00Z', completed_at: '2026-08-22T10:34:00Z' }),
    )
    const withoutStart = toMatchDetailData(
      detail({ started_at: null, completed_at: '2026-08-22T10:34:00Z' }),
    )
    // Different source timestamps must produce different formatted labels, proving started_at
    // was actually used rather than completed_at winning regardless.
    expect(withStart.playedAtLabel).not.toBe(withoutStart.playedAtLabel)
  })

  it('falls back to completed_at for playedAtLabel when started_at is null', () => {
    const result = toMatchDetailData(
      detail({ started_at: null, completed_at: '2026-08-22T10:34:00Z' }),
    )
    expect(result.playedAtLabel).not.toHaveLength(0)
  })

  it('carries captureStatus and captureDeadlineAt verbatim off the wire (T070e)', () => {
    const result = toMatchDetailData(
      detail({ capture_status: 'stored', capture_deadline_at: '2026-09-12T10:34:00Z' }),
    )
    expect(result.captureStatus).toBe('stored')
    expect(result.captureDeadlineAt).toBe('2026-09-12T10:34:00Z')
  })

  it('never collapses capture_status — every raw CaptureStatus value passes through unmodified', () => {
    // The badge's four-state collapse belongs to CaptureStateBadge, never this mapper
    // (capture-state-badge.md §3, mirrored from `toMatchRowData`'s identical rule).
    const result = toMatchDetailData(detail({ capture_status: 'quarantined' }))
    expect(result.captureStatus).toBe('quarantined')
  })

  it('carries capture_status/capture_deadline_at as null for a match with no capture row', () => {
    const result = toMatchDetailData(detail({ capture_status: null, capture_deadline_at: null }))
    expect(result.captureStatus).toBeNull()
    expect(result.captureDeadlineAt).toBeNull()
  })

  it('carries every participant, grouped by team, with none dropped or duplicated', () => {
    const result = toMatchDetailData(detail())
    const allIds = result.teams.flatMap((team) => team.participants.map((p) => p.id))
    expect(allIds.sort()).toEqual(['1', '2'])
  })
})
