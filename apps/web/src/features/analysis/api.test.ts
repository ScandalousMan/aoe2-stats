import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AnalysisResponseShapeError,
  assertAnalysisDocument,
  assertAnalysisSummary,
  extractAnalysisSummary,
  fetchPublishedAnalysis,
  assertPublishedAnalysis,
  assertAnalysisNames,
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

function validNames() {
  return { technology: { '101': 'Feudal Age', '999': null }, unit: {}, building: { '70': 'House' } }
}

describe('assertAnalysisNames', () => {
  it('accepts a table of names and nulls, empty kinds included', () => {
    expect(() => assertAnalysisNames(validNames())).not.toThrow()
  })

  it.each(['technology', 'unit', 'building'])('rejects a names table missing "%s"', (kind) => {
    const names: Record<string, unknown> = validNames()
    delete names[kind]
    expect(() => assertAnalysisNames(names)).toThrow(AnalysisResponseShapeError)
  })

  it('rejects a name that is neither a string nor null', () => {
    const names = { ...validNames(), unit: { '83': 7 } }
    expect(() => assertAnalysisNames(names)).toThrow(/names\.unit\.83 was not string\|null/)
  })

  it('rejects names that are not an object', () => {
    expect(() => assertAnalysisNames(null)).toThrow(AnalysisResponseShapeError)
    expect(() => assertAnalysisNames([])).toThrow(AnalysisResponseShapeError)
  })
})

describe('assertPublishedAnalysis', () => {
  it('accepts the {document, names} envelope', () => {
    expect(() =>
      assertPublishedAnalysis({ document: validDocument(), names: validNames() }),
    ).not.toThrow()
  })

  it('rejects the bare document the endpoint answered before T709', () => {
    expect(() => assertPublishedAnalysis(validDocument())).toThrow(AnalysisResponseShapeError)
  })

  it('rejects an envelope without names, and one whose document is malformed', () => {
    expect(() => assertPublishedAnalysis({ document: validDocument() })).toThrow(
      /"names" was not an object/,
    )
    const { engine: _engine, ...broken } = validDocument()
    expect(() => assertPublishedAnalysis({ document: broken, names: validNames() })).toThrow(
      /"engine" was not an object/,
    )
  })
})

describe('fetchPublishedAnalysis', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/matches/{game_id}/analysis and returns the validated document and names', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ document: validDocument(), names: validNames() }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const published = await fetchPublishedAnalysis(500_546_441)

    expect(published.document.participants).toHaveLength(1)
    expect(published.names.technology['101']).toBe('Feudal Age')
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
