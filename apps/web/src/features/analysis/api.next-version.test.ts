import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AnalysisResponseShapeError,
  assertAnalysisDocument,
  fetchAnalysisDocument,
  type ApiAnalysisDocument,
} from './api'

// T664 (US3, FR-007 to FR-011, FR-040 to FR-044): a regression pin, not a feature test. The
// document `specs/006-replay-analysis-foundations/contracts/analysis-document.md` publishes next
// is additive over the one `api.ts` reads today, and "The reader" section of that contract says
// this reader already accepts it with no source change. This file is what stops a later edit
// quietly breaking that — and it is why `extracted_at` is duplicated at its old top-level path
// rather than moved under `envelope`: the reader requires it there.
//
// Nothing here may need `api.ts` to change. If a case below goes red after an edit to the reader,
// the edit broke the seam; do not loosen the case.

/** Every existing field at its existing path, plus the contract's four added blocks, `envelope`,
 * a higher numeric `schema_version`, keys no reader knows, and the legacy top-level
 * `extracted_at`. Typed as a plain record: the reader's own type is deliberately narrower. */
function nextVersionDocument(): Record<string, unknown> {
  return {
    schema_version: 2,
    envelope: { extracted_at: '2026-10-03T10:00:00Z' },
    // Legacy path, kept for one version because the reader still requires it here.
    extracted_at: '2026-10-03T10:00:00Z',

    game_id: 500_546_441,
    point_of_view_profile_id: 196_240,
    engine: {
      name: 'aoe2rec-py',
      version: '0.1.21',
      deps: { 'aoe2rec-py': '0.1.21', 'aoc-mgz': '1.8.3' },
    },
    source_recording: {
      object_key: 'retained-recordings/500546441/196240.zip',
      sha256: 'a'.repeat(64),
    },
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

    // The four added blocks.
    identity: {
      digest: 'b'.repeat(64),
      recording: {
        object_key: 'retained-recordings/500546441/196240.zip',
        sha256: 'a'.repeat(64),
      },
      parser: { name: 'aoe2rec-py', version: '0.1.21' },
      parser_dependencies: { 'aoe2rec-py': '0.1.21', 'aoc-mgz': '1.8.3' },
      knowledge: {
        source: 'aoe2-data',
        source_version: '2026-09-30',
        describes_build: 168_000,
        digest: 'c'.repeat(64),
      },
      reconstruction_engine: 'not-applicable',
      analytics: '1',
    },
    provenance: {
      'participant.age_up_commands': { tier: 'observed', method: 'command-stream', inputs: [] },
    },
    inferred: {
      'participant.group_silence_episodes': [
        {
          participant: 1,
          from_ms: 0,
          units: 0,
          confidence: { level: 'medium', basis: 'a command-free stretch after a group order' },
          non_claim: 'not a casualty count — the recording carries no outcomes',
        },
      ],
    },
    knowledge_gaps: [
      {
        entity: { kind: 'unit', id: 0 },
        field: 'cost',
        build: 168_000,
        civilisation: 0,
        cause: 'civilisation-not-modelled',
        prevents: ['participant.resource_spend'],
        severity: 'blocking',
      },
    ],

    // Keys no version of this reader knows: ignored, never rejected.
    some_future_top_level_key: { nested: [1, 2, 3] },
    another_unknown_key: 'ignored',
  }
}

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

describe('the reader against the next document version (contracts/analysis-document.md)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses a version 2 document carrying the four added blocks, with no change to the reader', () => {
    const document = nextVersionDocument()
    expect(() => assertAnalysisDocument(document)).not.toThrow()
  })

  it('accepts any numeric schema_version, not only the one it was written against', () => {
    for (const schemaVersion of [1, 2, 3, 99]) {
      const document = { ...nextVersionDocument(), schema_version: schemaVersion }
      expect(() => assertAnalysisDocument(document)).not.toThrow()
    }
  })

  it('reads every existing field at its existing path', () => {
    const document = nextVersionDocument()
    assertAnalysisDocument(document)

    const typed: ApiAnalysisDocument = document
    expect(typed.schema_version).toBe(2)
    expect(typed.game_id).toBe(500_546_441)
    expect(typed.point_of_view_profile_id).toBe(196_240)
    expect(typed.engine.name).toBe('aoe2rec-py')
    expect(typed.engine.version).toBe('0.1.21')
    expect(typed.source_recording.object_key).toBe('retained-recordings/500546441/196240.zip')
    expect(typed.participants).toHaveLength(1)
    expect(typed.participants[0]?.age_up_commands).toEqual({ '101': 401_000 })
    // The legacy path, still read at the top level: this is why the field is duplicated.
    expect(typed.extracted_at).toBe('2026-10-03T10:00:00Z')
  })

  it('parses the same document end to end through fetchAnalysisDocument', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(nextVersionDocument()))
    vi.stubGlobal('fetch', fetchMock)

    const document = await fetchAnalysisDocument(500_546_441)

    expect(document.schema_version).toBe(2)
    expect(document.participants).toHaveLength(1)
  })

  it('ignores unknown keys: they are neither rejected nor required', () => {
    const withUnknown = nextVersionDocument()
    const without = { ...withUnknown }
    delete without.some_future_top_level_key
    delete without.another_unknown_key
    delete without.identity
    delete without.provenance
    delete without.inferred
    delete without.knowledge_gaps
    delete without.envelope

    expect(() => assertAnalysisDocument(withUnknown)).not.toThrow()
    // The added blocks are not required either: a version 1 shape still parses.
    expect(() => assertAnalysisDocument(without)).not.toThrow()
  })

  it('ignores unknown keys nested inside the participants it does read', () => {
    const document = nextVersionDocument()
    const participants = document.participants as Record<string, unknown>[]
    participants[0] = { ...participants[0], future_participant_key: { tier: 'observed' } }

    expect(() => assertAnalysisDocument(document)).not.toThrow()
  })

  // The contrast: the pin above is worthless if the reader simply accepts everything.
  describe('contrast: the reader is still strict about what it does require', () => {
    it('rejects a next-version document missing the legacy top-level extracted_at', () => {
      const document = nextVersionDocument()
      delete document.extracted_at

      // `envelope.extracted_at` is present and does not stand in for it.
      expect(() => assertAnalysisDocument(document)).toThrow(AnalysisResponseShapeError)
      expect(() => assertAnalysisDocument(document)).toThrow(/"extracted_at" was not a string/)
    })

    it('rejects a next-version document missing a required existing field', () => {
      for (const field of [
        'schema_version',
        'game_id',
        'point_of_view_profile_id',
        'engine',
        'source_recording',
        'participants',
      ]) {
        const document = nextVersionDocument()
        delete document[field]

        expect(() => assertAnalysisDocument(document), field).toThrow(AnalysisResponseShapeError)
      }
    })

    it('rejects a next-version document whose schema_version is not numeric', () => {
      const document = { ...nextVersionDocument(), schema_version: '2' }

      expect(() => assertAnalysisDocument(document)).toThrow(/"schema_version" was not a number/)
    })

    it('rejects a participant missing a field the reader requires', () => {
      const document = nextVersionDocument()
      const participants = document.participants as Record<string, unknown>[]
      const { age_up_commands: _dropped, ...rest } = participants[0] as Record<string, unknown>
      participants[0] = rest

      expect(() => assertAnalysisDocument(document)).toThrow(
        /participants\[0\]\.age_up_commands was not an object/,
      )
    })

    it('rejects, through fetchAnalysisDocument, a document missing a required field', async () => {
      const document = nextVersionDocument()
      delete document.engine
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => jsonResponse(document)),
      )

      await expect(fetchAnalysisDocument(500_546_441)).rejects.toBeInstanceOf(
        AnalysisResponseShapeError,
      )
    })
  })
})
