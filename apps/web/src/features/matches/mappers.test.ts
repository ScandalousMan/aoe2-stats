import { describe, expect, it } from 'vitest'
import type {
  ApiMatchDetail,
  ApiMatchListRow,
  ApiMatchParticipant,
  ApiMatchRowParticipant,
  ApiOpponent,
} from './api'
import {
  toMatchDetailData,
  toMatchRowData,
  toMatchRowDataList,
  toMatchRowParticipant,
  toParticipantData,
  toTeamGroups,
} from './mappers'

function opponent(overrides: Partial<ApiOpponent> = {}): ApiOpponent {
  return { profile_id: 2, alias: 'Rival', civ_id: 3, civ_name: 'Celts', ...overrides }
}

function rowParticipant(overrides: Partial<ApiMatchRowParticipant> = {}): ApiMatchRowParticipant {
  return {
    profile_id: 1,
    alias: 'Me',
    country: 'fr',
    team_id: 1,
    civ_id: 7,
    civ_name: 'Japanese',
    color_id: 4,
    result: 'win',
    rating: 934,
    rating_diff: 12,
    ...overrides,
  }
}

function row(overrides: Partial<ApiMatchListRow> = {}): ApiMatchListRow {
  return {
    game_id: 123,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    civilisation: 7,
    civilisation_name: 'Japanese',
    result: 'win',
    rating: 934,
    rating_diff: 12,
    team_id: 1,
    color_id: 4,
    opponents: [opponent()],
    participants: [
      rowParticipant(),
      rowParticipant({
        profile_id: 2,
        alias: 'Rival',
        team_id: 2,
        civ_id: 3,
        civ_name: 'Celts',
        color_id: 2,
        result: 'loss',
        rating: 1500,
        rating_diff: -12,
      }),
    ],
    capture_status: 'stored',
    capture_deadline_at: null,
    ...overrides,
  }
}

// The profile whose history this page is — `mappers.ts`'s own doc: computed once, upstream, never
// guessed. `rowParticipant()`'s default `profile_id: 1` is this fixture's own viewer.
const VIEWER_PROFILE_ID = 1

describe('toMatchRowParticipant', () => {
  it('flags the participant whose profile_id matches the viewer, and no other', () => {
    const viewer = toMatchRowParticipant(rowParticipant({ profile_id: 1 }), 1)
    const other = toMatchRowParticipant(rowParticipant({ profile_id: 2 }), 1)
    expect(viewer.isViewer).toBe(true)
    expect(other.isViewer).toBe(false)
  })

  it('falls back to a placeholder alias for a null alias, never the literal null', () => {
    expect(toMatchRowParticipant(rowParticipant({ alias: null }), 1).alias).toBe('Unknown player')
  })

  it('narrows an unrecognised result to null, never a guessed loss', () => {
    expect(toMatchRowParticipant(rowParticipant({ result: 'draw' }), 1).result).toBeNull()
  })
})

describe('toMatchRowData', () => {
  it('maps game_id to a string gameId and builds the T076 detail href', () => {
    const result = toMatchRowData(row({ game_id: 456 }), VIEWER_PROFILE_ID)
    expect(result.gameId).toBe('456')
    expect(result.href).toBe('/matches/456')
  })

  it('maps a win result to the "win" outcome', () => {
    expect(toMatchRowData(row({ result: 'win' }), VIEWER_PROFILE_ID).outcome).toBe('win')
  })

  it('maps a loss result to the "loss" outcome', () => {
    expect(toMatchRowData(row({ result: 'loss' }), VIEWER_PROFILE_ID).outcome).toBe('loss')
  })

  // match-history.md §2a: `match_players.result` is `null` for every row this system has written
  // so far — the outcome must read "unknown", never a guessed "loss" (the reported defect).
  it('maps a null result to the "unknown" outcome, never "loss"', () => {
    expect(toMatchRowData(row({ result: null }), VIEWER_PROFILE_ID).outcome).toBe('unknown')
  })

  it('carries a positive rating_diff as a StatValueDelta', () => {
    const result = toMatchRowData(row({ rating_diff: 18 }), VIEWER_PROFILE_ID)
    expect(result.ratingChange).toEqual({ value: 18, formatted: '18' })
  })

  it('carries a negative rating_diff with a positive formatted magnitude', () => {
    const result = toMatchRowData(row({ rating_diff: -9 }), VIEWER_PROFILE_ID)
    expect(result.ratingChange).toEqual({ value: -9, formatted: '9' })
  })

  it('omits ratingChange entirely when there is nothing to report', () => {
    const result = toMatchRowData(row({ rating_diff: null }), VIEWER_PROFILE_ID)
    expect(result.ratingChange).toBeUndefined()
  })

  it('falls back to "Unknown map" for a null map_name', () => {
    expect(toMatchRowData(row({ map_name: null }), VIEWER_PROFILE_ID).map).toBe('Unknown map')
  })

  it('passes the server-named civilisation through (T070c), not the raw id', () => {
    expect(
      toMatchRowData(row({ civilisation_name: 'Turks' }), VIEWER_PROFILE_ID).civilisation,
    ).toBe('Turks')
  })

  it('falls back to "Unknown civilisation" for a null civilisation_name', () => {
    expect(toMatchRowData(row({ civilisation_name: null }), VIEWER_PROFILE_ID).civilisation).toBe(
      'Unknown civilisation',
    )
  })

  it("passes capture_status and capture_deadline_at through unmodified — the collapse is the badge's job", () => {
    const result = toMatchRowData(
      row({ capture_status: 'pending', capture_deadline_at: '2026-09-01T00:00:00Z' }),
      VIEWER_PROFILE_ID,
    )
    expect(result.captureStatus).toBe('pending')
    expect(result.captureDeadlineAt).toBe('2026-09-01T00:00:00Z')
  })

  it('passes a null capture_status through as null, never a guessed default', () => {
    expect(
      toMatchRowData(row({ capture_status: null }), VIEWER_PROFILE_ID).captureStatus,
    ).toBeNull()
  })

  // match-history.md §12.3: every participant is carried through, the viewer flagged.
  it('maps every participant, flagging the viewer among them', () => {
    const result = toMatchRowData(row(), VIEWER_PROFILE_ID)
    expect(result.participants).toHaveLength(2)
    expect(result.participants?.find((p) => p.isViewer)?.alias).toBe('Me')
  })
})

describe('toMatchRowDataList', () => {
  it('maps an empty list to an empty list', () => {
    expect(toMatchRowDataList([], VIEWER_PROFILE_ID)).toEqual([])
  })

  it('maps every row in order', () => {
    const result = toMatchRowDataList([row({ game_id: 1 }), row({ game_id: 2 })], VIEWER_PROFILE_ID)
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
    replay: {
      profile_id: 2,
      availability: 'obtainable',
      obtainable_until: null,
      download_path: '/api/matches/700800900/replay/2',
    },
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
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    patch: '101.101',
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

  it('passes civ_id and civ_name through separately, never a single pre-formatted string', () => {
    const result = toParticipantData(participant({ civ_id: 9, civ_name: 'Turks' }))
    expect(result.civId).toBe(9)
    expect(result.civName).toBe('Turks')
  })

  it('§11.2: carries civId with a null civName rather than inventing a fallback name', () => {
    const result = toParticipantData(participant({ civ_id: 87, civ_name: null }))
    expect(result.civId).toBe(87)
    expect(result.civName).toBeNull()
  })

  it('maps a win result to the "win" outcome', () => {
    expect(toParticipantData(participant({ result: 'win' })).result).toBe('win')
  })

  it('maps a loss result to the "loss" outcome', () => {
    expect(toParticipantData(participant({ result: 'loss' })).result).toBe('loss')
  })

  // match-history.md §2a: the same rule `toMatchRowData` follows above — a participant's own
  // result is `null` for every row this system has written so far, and must read "unknown", never
  // a guessed "loss" (the reported production defect, an eight-player match shown as eight
  // losses).
  it('maps a null result to the "unknown" outcome, never a guessed "loss"', () => {
    expect(toParticipantData(participant({ result: null })).result).toBe('unknown')
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

  it('passes a resolved map_name through unmodified', () => {
    expect(toMatchDetailData(detail({ map_name: 'Arena' })).map).toBe('Arena')
  })

  it('§11.2: carries a null map_name through as null, never a fabricated "Unknown map"', () => {
    expect(toMatchDetailData(detail({ map_name: null })).map).toBeNull()
  })

  it('passes patch through as gameVersion, verbatim (FR-018)', () => {
    expect(toMatchDetailData(detail({ patch: '101.101' })).gameVersion).toBe('101.101')
  })

  it('carries a null patch through as a null gameVersion', () => {
    expect(toMatchDetailData(detail({ patch: null })).gameVersion).toBeNull()
  })

  it('passes the server-named leaderboard through unmodified (T070f)', () => {
    expect(toMatchDetailData(detail({ leaderboard_name: 'Team Random Map' })).leaderboardName).toBe(
      'Team Random Map',
    )
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
