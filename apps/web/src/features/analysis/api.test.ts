import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AnalysisResponseShapeError,
  assertAnalysisDocument,
  assertAnalysisSummary,
  extractAnalysisSummary,
  fetchAnalysisDocument,
  readDocumentNames,
  readKnowledgeNames,
  requestAnalysis,
  type ApiAnalysisDocument,
} from './api'

// T037a's rule, applied to the two shapes this feature reads: `analysis` on `GET /api/matches/
// {game_id}` (`routers/matches.py`'s `_analysis_json`) and the document `GET /api/matches/
// {game_id}/analysis` answers (`contracts/analysis.md`'s "The published analysis").

function validSummary() {
  return {
    state: 'published' as const,
    parser_version: '0.1.21',
    stale: false,
    point_of_view_profile_id: 196_240,
    result_path: '/api/matches/500546441/analysis',
    reason: null,
    error_class: null,
  }
}

function validDocument(): ApiAnalysisDocument {
  return {
    schema_version: 1,
    game_id: 500_546_441,
    point_of_view_profile_id: 196_240,
    engine: { name: 'aoe2rec-py', version: '0.1.21', deps: {} },
    source_recording: {
      object_key: 'retained-recordings/500546441/196240.zip',
      sha256: 'a'.repeat(64),
    },
    extracted_at: '2026-08-23T10:00:00Z',
    participants: [
      {
        profile_id: 196_240,
        player_number: 1,
        civ_id: 5,
        resolved_team_id: 1,
        builds: [{ building_id: 70, world_time_ms: 15_000 }],
        trainings: [{ unit_id: 83, amount: 3, building_id: 109, world_time_ms: 42_000 }],
        researches: [{ technology_id: 22, world_time_ms: 20_000 }],
        age_up_commands: { '101': 401_000 },
        villagers_ordered: 68,
        actions: 3821,
        actions_per_minute: 142.7,
        resigned_at_ms: null,
      },
    ],
  }
}

describe('assertAnalysisSummary', () => {
  it('accepts a well-formed summary in every one of the seven states', () => {
    for (const state of [
      'absent',
      'queued',
      'running',
      'published',
      'failed',
      'unavailable',
      'refused',
    ] as const) {
      expect(() => assertAnalysisSummary({ ...validSummary(), state })).not.toThrow()
    }
  })

  it('accepts null parser_version, point_of_view_profile_id and reason (never-requested / absent)', () => {
    expect(() =>
      assertAnalysisSummary({
        state: 'absent',
        parser_version: null,
        stale: false,
        point_of_view_profile_id: null,
        result_path: '/api/matches/1/analysis',
        reason: null,
        error_class: null,
      }),
    ).not.toThrow()
  })

  it('accepts a string error_class and rejects a missing or non-string one (T706b)', () => {
    expect(() =>
      assertAnalysisSummary({
        ...validSummary(),
        state: 'failed',
        error_class: 'EngineParseError',
      }),
    ).not.toThrow()
    const { error_class: _omitted, ...withoutErrorClass } = validSummary()
    expect(() => assertAnalysisSummary(withoutErrorClass)).toThrow(AnalysisResponseShapeError)
    expect(() => assertAnalysisSummary({ ...validSummary(), error_class: 7 })).toThrow(
      AnalysisResponseShapeError,
    )
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertAnalysisSummary(null)).toThrow(AnalysisResponseShapeError)
    expect(() => assertAnalysisSummary('nope')).toThrow(AnalysisResponseShapeError)
  })

  it('rejects a state outside the seven known values', () => {
    expect(() => assertAnalysisSummary({ ...validSummary(), state: 'bogus' })).toThrow(
      AnalysisResponseShapeError,
    )
  })

  it('rejects a non-boolean stale', () => {
    expect(() => assertAnalysisSummary({ ...validSummary(), stale: 'true' })).toThrow(
      AnalysisResponseShapeError,
    )
  })

  it('rejects a missing result_path', () => {
    const summary = validSummary() as Record<string, unknown>
    delete summary.result_path
    expect(() => assertAnalysisSummary(summary)).toThrow(AnalysisResponseShapeError)
  })
})

describe('extractAnalysisSummary', () => {
  it('reads the "analysis" object off a match-detail payload', () => {
    const payload = { game_id: 1, analysis: validSummary() }
    expect(extractAnalysisSummary(payload)).toEqual(validSummary())
  })

  it('throws for a payload carrying no "analysis" object at all', () => {
    expect(() => extractAnalysisSummary({ game_id: 1 })).toThrow(AnalysisResponseShapeError)
  })

  it('throws for a payload that is not an object', () => {
    expect(() => extractAnalysisSummary(null)).toThrow(AnalysisResponseShapeError)
  })
})

describe('assertAnalysisDocument', () => {
  it('accepts a well-formed published document', () => {
    expect(() => assertAnalysisDocument(validDocument())).not.toThrow()
  })

  it('accepts an empty age_up_commands object and empty event lists', () => {
    const document = validDocument()
    document.participants[0]!.age_up_commands = {}
    document.participants[0]!.builds = []
    document.participants[0]!.trainings = []
    document.participants[0]!.researches = []
    expect(() => assertAnalysisDocument(document)).not.toThrow()
  })

  it('accepts a resigned participant', () => {
    const document = validDocument()
    document.participants[0]!.resigned_at_ms = 1_680_000
    expect(() => assertAnalysisDocument(document)).not.toThrow()
  })

  it('rejects a body that is not an object', () => {
    expect(() => assertAnalysisDocument(null)).toThrow(AnalysisResponseShapeError)
  })

  it('rejects a participant missing resolved_team_id', () => {
    const document = validDocument() as unknown as { participants: Array<Record<string, unknown>> }
    delete document.participants[0]!.resolved_team_id
    expect(() => assertAnalysisDocument(document)).toThrow(AnalysisResponseShapeError)
  })

  it('rejects a build event with a non-numeric world_time_ms', () => {
    const document = validDocument()
    // @ts-expect-error deliberately malformed for this test
    document.participants[0]!.builds[0]!.world_time_ms = '15000'
    expect(() => assertAnalysisDocument(document)).toThrow(AnalysisResponseShapeError)
  })

  it('rejects an age_up_commands entry with a non-numeric value', () => {
    const document = validDocument() as unknown as {
      participants: Array<{ age_up_commands: Record<string, unknown> }>
    }
    document.participants[0]!.age_up_commands = { '101': 'soon' }
    expect(() => assertAnalysisDocument(document)).toThrow(AnalysisResponseShapeError)
  })
})

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

describe('fetchAnalysisDocument', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/matches/{game_id}/analysis and returns the validated document', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(validDocument()))
    vi.stubGlobal('fetch', fetchMock)

    const document = await fetchAnalysisDocument(500_546_441)

    expect(document.participants).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      '/api/matches/500546441/analysis',
      expect.objectContaining({ method: 'GET' }),
    )
  })
})

describe('requestAnalysis', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs /api/analyze with the game_id and returns the validated summary', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(validSummary()))
    vi.stubGlobal('fetch', fetchMock)

    const summary = await requestAnalysis(500_546_441)

    expect(summary.state).toBe('published')
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      '/api/analyze',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ game_id: 500_546_441 }),
      }),
    )
  })
})

describe('readKnowledgeNames', () => {
  const valid = {
    snapshot: { describes_build: 180_059, digest: 'sha256:abc' },
    technology: { '101': 'Feudal Age' },
    unit: {},
    building: { '70': 'House' },
  }

  it('reads a well-formed block as it is', () => {
    expect(readKnowledgeNames(valid)).toEqual(valid)
  })

  it('reads an absent block as no names', () => {
    expect(readKnowledgeNames(undefined)).toBeNull()
    expect(readKnowledgeNames(null)).toBeNull()
  })

  it.each([
    ['a non-object', 'Feudal Age'],
    ['a missing kind', { ...valid, unit: undefined }],
    ['a non-string name', { ...valid, technology: { '101': 101 } }],
    ['an array for a kind', { ...valid, building: ['House'] }],
    ['a missing snapshot record', { ...valid, snapshot: undefined }],
    ['a non-numeric build', { ...valid, snapshot: { describes_build: '180059', digest: 'x' } }],
  ])('reads %s as no names, not as a partial answer', (_label, block) => {
    expect(readKnowledgeNames(block)).toBeNull()
  })

  it('does not make a document that carries names, or a malformed block, fail validation', () => {
    const document = {
      schema_version: 2,
      game_id: 1,
      point_of_view_profile_id: 1,
      engine: { name: 'aoe2rec-py', version: '0.1.21', deps: {} },
      source_recording: { object_key: 'k', sha256: 'a'.repeat(64) },
      extracted_at: '2026-08-23T10:00:00Z',
      participants: [],
    }
    expect(() => assertAnalysisDocument({ ...document, knowledge_names: valid })).not.toThrow()
    expect(() => assertAnalysisDocument({ ...document, knowledge_names: 'garbage' })).not.toThrow()
  })
})

describe('readKnowledgeNames and the block provenance (T709a)', () => {
  const valid = {
    snapshot: { describes_build: 180_059, digest: 'sha256:abc' },
    technology: { '101': 'Feudal Age' },
    unit: {},
    building: {},
  }
  const provenance = {
    'names.technology': {
      tier: 'derived',
      method: 'knowledge-snapshot.name@2',
      inputs: ['participant.researches.technology_id'],
    },
  }

  it('accepts a block that carries the provenance key', () => {
    expect(readKnowledgeNames({ ...valid, provenance })).toEqual(valid)
  })

  it.each([
    ['a string', 'garbage'],
    ['an array', []],
    ['null', null],
    ['an entry that is not an object', { 'names.technology': 7 }],
  ])('still renders its names when the provenance is %s', (_label, bad) => {
    expect(readKnowledgeNames({ ...valid, provenance: bad })).toEqual(valid)
  })
})

describe('readDocumentNames', () => {
  const block = {
    snapshot: { describes_build: 180_059, digest: 'sha256:abc' },
    technology: { '101': 'Feudal Age' },
    unit: {},
    building: {},
  }
  const identity = { knowledge: { describes_build: 180_059, digest: 'sha256:abc' } }

  it('accepts a block whose snapshot is the one the document identity names', () => {
    expect(readDocumentNames({ identity, knowledge_names: block })).toEqual(block)
  })

  it('ignores a block whose snapshot digest differs from the identity', () => {
    const other = { knowledge: { describes_build: 180_059, digest: 'sha256:def' } }
    expect(readDocumentNames({ identity: other, knowledge_names: block })).toBeNull()
  })

  it('ignores a block whose snapshot build differs from the identity', () => {
    const other = { knowledge: { describes_build: 185_872, digest: 'sha256:abc' } }
    expect(readDocumentNames({ identity: other, knowledge_names: block })).toBeNull()
  })

  it('ignores a block beside an identity that names no snapshot, or none at all', () => {
    const absent = { knowledge: { absent: 'no-snapshot-for-build', build: 180_059 } }
    expect(readDocumentNames({ identity: absent, knowledge_names: block })).toBeNull()
    expect(readDocumentNames({ identity: null, knowledge_names: block })).toBeNull()
    expect(readDocumentNames({ knowledge_names: block })).toBeNull()
  })

  it('reads no names when the block is absent or malformed', () => {
    expect(readDocumentNames({ identity })).toBeNull()
    expect(readDocumentNames({ identity, knowledge_names: 'garbage' })).toBeNull()
  })
})
