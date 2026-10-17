import { describe, expect, it } from 'vitest'
import type { ApiMatchParticipant } from '../matches/api'
import type { ApiAnalysisDocument, ApiAnalysisDocumentParticipant, ApiAnalysisNames } from './api'
import { toAnalysisParticipantData, toAnalysisTeamGroups } from './mappers'

function matchParticipant(overrides: Partial<ApiMatchParticipant> = {}): ApiMatchParticipant {
  return {
    profile_id: 196_240,
    alias: 'GL.TheViper',
    team_id: 1,
    civ_id: 5,
    civ_name: 'Britons',
    color_id: 1,
    result: 'win',
    rating: 1900,
    rating_diff: 12,
    replay: {
      profile_id: 196_240,
      availability: 'obtainable',
      obtainable_until: null,
      download_path: '/api/matches/500546441/replay/196240',
    },
    ...overrides,
  }
}

function docParticipant(
  overrides: Partial<ApiAnalysisDocumentParticipant> = {},
): ApiAnalysisDocumentParticipant {
  return {
    profile_id: 196_240,
    player_number: 1,
    civ_id: 5,
    resolved_team_id: 1,
    builds: [],
    trainings: [],
    researches: [],
    age_up_commands: {},
    villagers_ordered: 68,
    actions: 3821,
    actions_per_minute: 142.7,
    resigned_at_ms: null,
    ...overrides,
  }
}

function document(participants: ApiAnalysisDocumentParticipant[]): ApiAnalysisDocument {
  return {
    schema_version: 1,
    game_id: 500_546_441,
    point_of_view_profile_id: 196_240,
    engine: { name: 'aoe2rec-py', version: '0.1.21', deps: {} },
    source_recording: { object_key: 'k', sha256: 'a'.repeat(64) },
    extracted_at: '2026-08-23T10:00:00Z',
    participants,
  }
}

const NO_NAMES: ApiAnalysisNames = { technology: {}, unit: {}, building: {} }

// What `routers/analysis.py` serves for a build 185872 document (T709): real names for ids the
// snapshot names and `null` for one it does not.
const NAMES: ApiAnalysisNames = {
  technology: { '101': 'Feudal Age', '102': 'Castle Age', '22': 'Loom', '999': null },
  unit: { '83': 'Villager', '998': null },
  building: { '70': 'House', '997': null },
}

describe('toAnalysisParticipantData', () => {
  it('joins alias and civ_name from the matching match-detail participant', () => {
    const data = toAnalysisParticipantData(docParticipant(), matchParticipant(), NO_NAMES)
    expect(data.alias).toBe('GL.TheViper')
    expect(data.civName).toBe('Britons')
    expect(data.civId).toBe(5)
  })

  it('falls back to "Unknown player" and a null civName when no match participant joins', () => {
    const data = toAnalysisParticipantData(docParticipant(), undefined, NO_NAMES)
    expect(data.alias).toBe('Unknown player')
    expect(data.civName).toBeNull()
  })

  it('renders the names the API resolved for technology, unit and building ids (T709)', () => {
    const data = toAnalysisParticipantData(
      docParticipant({
        builds: [{ building_id: 70, world_time_ms: 15_000 }],
        trainings: [{ unit_id: 83, amount: 3, building_id: 109, world_time_ms: 42_000 }],
        researches: [{ technology_id: 22, world_time_ms: 20_000 }],
        age_up_commands: { '101': 401_000, '102': 720_000 },
      }),
      matchParticipant(),
      NAMES,
    )
    expect(data.builds[0]?.buildingName).toBe('House')
    expect(data.trainings[0]?.unitName).toBe('Villager')
    expect(data.researches[0]?.technologyName).toBe('Loom')
    expect(data.ageUps.map((row) => row.ageName)).toEqual(['Feudal Age', 'Castle Age'])
  })

  it('leaves an id the snapshot does not name unresolved, whether null or absent from the table (FR-043a)', () => {
    const data = toAnalysisParticipantData(
      docParticipant({
        builds: [
          { building_id: 997, world_time_ms: 1 },
          { building_id: 996, world_time_ms: 2 },
        ],
        trainings: [{ unit_id: 998, amount: 1, building_id: 109, world_time_ms: 3 }],
        researches: [{ technology_id: 999, world_time_ms: 4 }],
        age_up_commands: { '103': 5 },
      }),
      matchParticipant(),
      NAMES,
    )
    // 997 is `null` in the table, 996 is not in it at all; neither becomes a name, and the id is
    // never echoed as one.
    expect(data.builds.map((row) => row.buildingName)).toEqual([null, null])
    expect(data.trainings[0]?.unitName).toBeNull()
    expect(data.researches[0]?.technologyName).toBeNull()
    expect(data.ageUps[0]?.ageName).toBeNull()
  })

  it('looks each id up in its own kind: technology 70 is not building 70', () => {
    const data = toAnalysisParticipantData(
      docParticipant({
        builds: [{ building_id: 101, world_time_ms: 1 }],
        researches: [{ technology_id: 70, world_time_ms: 2 }],
      }),
      matchParticipant(),
      NAMES,
    )
    expect(data.builds[0]?.buildingName).toBeNull()
    expect(data.researches[0]?.technologyName).toBeNull()
  })

  it('carries the amount for a training event straight through (a DeQueue can queue more than one)', () => {
    const data = toAnalysisParticipantData(
      docParticipant({
        trainings: [{ unit_id: 83, amount: 3, building_id: 109, world_time_ms: 42_000 }],
      }),
      matchParticipant(),
      NO_NAMES,
    )
    expect(data.trainings[0]).toMatchObject({ amount: 3, timeMs: 42_000, unitId: 83 })
  })

  it('carries villagersOrdered, apm and actions straight through — no reconstruction (FR-043b)', () => {
    const data = toAnalysisParticipantData(
      docParticipant({ villagers_ordered: 68, actions: 3821, actions_per_minute: 142.7 }),
      matchParticipant(),
      NO_NAMES,
    )
    expect(data.villagersOrdered).toBe(68)
    expect(data.actions).toBe(3821)
    expect(data.apm).toBeCloseTo(142.7)
  })

  it('carries resignedAtMs through, null when the participant never resigned', () => {
    expect(
      toAnalysisParticipantData(docParticipant(), matchParticipant(), NO_NAMES).resignedAtMs,
    ).toBeNull()
    expect(
      toAnalysisParticipantData(
        docParticipant({ resigned_at_ms: 1_680_000 }),
        matchParticipant(),
        NO_NAMES,
      ).resignedAtMs,
    ).toBe(1_680_000)
  })

  it('orders age-up rows chronologically, oldest first (§3.1)', () => {
    const data = toAnalysisParticipantData(
      docParticipant({ age_up_commands: { '103': 1_200_000, '101': 401_000, '102': 720_000 } }),
      matchParticipant(),
      NO_NAMES,
    )
    expect(data.ageUps.map((row) => row.technologyId)).toEqual([101, 102, 103])
  })
})

describe('toAnalysisTeamGroups', () => {
  it('carries the names through to every participant', () => {
    const teams = toAnalysisTeamGroups(
      document([docParticipant({ profile_id: 1, age_up_commands: { '101': 5 } })]),
      [matchParticipant({ profile_id: 1 })],
      NAMES,
    )
    expect(teams[0]?.participants[0]?.ageUps[0]?.ageName).toBe('Feudal Age')
  })

  it('groups participants by resolved_team_id, in first-seen order', () => {
    const teams = toAnalysisTeamGroups(
      document([
        docParticipant({ profile_id: 1, resolved_team_id: 2 }),
        docParticipant({ profile_id: 2, resolved_team_id: 1 }),
        docParticipant({ profile_id: 3, resolved_team_id: 2 }),
      ]),
      [
        matchParticipant({ profile_id: 1, alias: 'p1' }),
        matchParticipant({ profile_id: 2, alias: 'p2' }),
        matchParticipant({ profile_id: 3, alias: 'p3' }),
      ],
      NO_NAMES,
    )

    expect(teams.map((team) => team.id)).toEqual(['team-2', 'team-1'])
    expect(teams[0]?.participants.map((p) => p.alias)).toEqual(['p1', 'p3'])
    expect(teams[1]?.participants.map((p) => p.alias)).toEqual(['p2'])
  })

  it('returns one team group per resolved_team_id even for a single-participant document', () => {
    const teams = toAnalysisTeamGroups(
      document([docParticipant({ profile_id: 1 })]),
      [matchParticipant({ profile_id: 1 })],
      NO_NAMES,
    )
    expect(teams).toHaveLength(1)
    expect(teams[0]?.participants).toHaveLength(1)
  })
})
