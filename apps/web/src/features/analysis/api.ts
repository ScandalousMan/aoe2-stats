import { queryOptions } from '@tanstack/react-query'
import { api } from '../../lib/api'

// T372, US4: the analysis summary carried on `GET /api/matches/{game_id}` (`routers/matches.py`'s
// `_analysis_json`, T368) and the published document served whole by `GET /api/matches/{game_id}/
// analysis` (`routers/analysis.py`, T368) — `contracts/http-api.md`'s "Analysis" section and
// `contracts/analysis.md`'s "The published analysis" section are ground truth for both shapes.
//
// This module deliberately does not import anything from `features/matches/api.ts` for the
// summary object: `ApiMatchDetail` there does not declare an `analysis` field at all (T331/T338
// shipped before T368 added it to the wire response), so this module reads it straight off the
// same raw JSON payload `matchDetailQueryOptions`'s `queryFn` already fetched and cached — the
// exact `analysis` key `_analysis_json` puts in the body — and validates it independently, the
// same "self-contained, not an import" discipline `routers/analysis.py`'s own module docstring
// states for its Python counterpart. `AnalysisContainer.tsx` shares `matchDetailQueryOptions`'s
// query key so the two containers issue one request, not two.

/** The seven values `contracts/http-api.md`'s `analysis.state` carries. `AnalysisTimeline`
 * (packages/design-system) renders six of them; `absent` is this feature's own "Request analysis"
 * button, wired directly here (`analysis-timeline.md` §1). */
export type AnalysisState =
  'absent' | 'queued' | 'running' | 'published' | 'failed' | 'unavailable' | 'refused'

const ANALYSIS_STATES: readonly AnalysisState[] = [
  'absent',
  'queued',
  'running',
  'published',
  'failed',
  'unavailable',
  'refused',
]

/** `routers/matches.py`'s `_analysis_json` — every field name verbatim off the wire, snake_case,
 * the same convention every other module in this feature documents. `stale` is computed there on
 * every read (FR-041), never a stored column, and is only ever `true` while `state === 'published'`. */
export interface ApiAnalysisSummary {
  state: AnalysisState
  parser_version: string | null
  stale: boolean
  point_of_view_profile_id: number | null
  result_path: string
  reason: string | null
}

/** Thrown when the `analysis` object on `GET /api/matches/{game_id}`, or the document `GET
 * /api/matches/{game_id}/analysis` answers, does not match the shape this module declares —
 * mirrors `MatchDetailResponseShapeError` (`features/matches/api.ts`) and `ApiResponseShapeError`
 * (`lib/api.ts`, T037a): a network response the compiler can never check on its own. */
export class AnalysisResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected analysis response shape: ${detail}`)
    this.name = 'AnalysisResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

/** Validates and narrows the `analysis` object at `path` (default `"analysis"`, the key on the
 * match-detail response; `fetchAnalysisSummaryStandalone` below never needs a different one). */
export function assertAnalysisSummary(
  value: unknown,
  path = 'analysis',
): asserts value is ApiAnalysisSummary {
  if (typeof value !== 'object' || value === null) {
    throw new AnalysisResponseShapeError(`"${path}" was not an object`)
  }
  const summary = value as Record<string, unknown>
  if (
    typeof summary.state !== 'string' ||
    !ANALYSIS_STATES.includes(summary.state as AnalysisState)
  ) {
    throw new AnalysisResponseShapeError(`"${path}.state" was not one of the seven known states`)
  }
  if (!isNullableString(summary.parser_version)) {
    throw new AnalysisResponseShapeError(`"${path}.parser_version" was not string|null`)
  }
  if (typeof summary.stale !== 'boolean') {
    throw new AnalysisResponseShapeError(`"${path}.stale" was not a boolean`)
  }
  if (!isNullableNumber(summary.point_of_view_profile_id)) {
    throw new AnalysisResponseShapeError(`"${path}.point_of_view_profile_id" was not number|null`)
  }
  if (typeof summary.result_path !== 'string') {
    throw new AnalysisResponseShapeError(`"${path}.result_path" was not a string`)
  }
  if (!isNullableString(summary.reason)) {
    throw new AnalysisResponseShapeError(`"${path}.reason" was not string|null`)
  }
}

/** Reads the `analysis` object off an already-fetched `GET /api/matches/{game_id}` payload
 * (`matchDetailQueryOptions`'s own cached data, `features/matches/api.ts`) — module docstring's
 * "reads it straight off the same raw JSON payload." Throws `AnalysisResponseShapeError` for a
 * payload carrying no `analysis` object at all or one that fails validation. */
export function extractAnalysisSummary(matchDetailPayload: unknown): ApiAnalysisSummary {
  if (typeof matchDetailPayload !== 'object' || matchDetailPayload === null) {
    throw new AnalysisResponseShapeError('match-detail response was not an object')
  }
  const body = matchDetailPayload as Record<string, unknown>
  assertAnalysisSummary(body.analysis)
  return body.analysis as ApiAnalysisSummary
}

// --- The published document, GET /api/matches/{game_id}/analysis (FR-030, contracts/analysis.md) --

export interface ApiAnalysisBuildEvent {
  building_id: number
  world_time_ms: number
}

export interface ApiAnalysisTrainingEvent {
  unit_id: number
  amount: number
  building_id: number
  world_time_ms: number
}

export interface ApiAnalysisResearchEvent {
  technology_id: number
  world_time_ms: number
}

/** `MatchTimeline.participants` (`contracts/analysis.md`) — every field name is load-bearing
 * there (that contract's own "Every name in there is load-bearing" section) and unchanged here.
 * Carries no `alias` or resolved name of any kind: those come from the match-detail participant
 * with the same `profile_id`, joined in `mappers.ts`, never invented here. */
export interface ApiAnalysisDocumentParticipant {
  profile_id: number
  player_number: number
  civ_id: number
  resolved_team_id: number
  builds: ApiAnalysisBuildEvent[]
  trainings: ApiAnalysisTrainingEvent[]
  researches: ApiAnalysisResearchEvent[]
  /** `age_up_commands` — a JSON object keyed by the stringified technology id (101/102/103),
   * valued by the command's `world_time_ms` (`contracts/analysis.md`). */
  age_up_commands: Record<string, number>
  villagers_ordered: number
  actions: number
  actions_per_minute: number
  resigned_at_ms: number | null
}

export interface ApiAnalysisEngine {
  name: string
  version: string
  deps: Record<string, unknown>
}

export interface ApiAnalysisSourceRecording {
  object_key: string
  sha256: string
}

/** `contracts/analysis.md`'s "The published analysis" — `MatchTimeline` serialised plus the
 * provenance that makes FR-041 mechanical. */
export interface ApiAnalysisDocument {
  schema_version: number
  game_id: number
  point_of_view_profile_id: number
  engine: ApiAnalysisEngine
  source_recording: ApiAnalysisSourceRecording
  extracted_at: string
  participants: ApiAnalysisDocumentParticipant[]
}

function assertAnalysisBuildEvent(
  value: unknown,
  path: string,
): asserts value is ApiAnalysisBuildEvent {
  if (typeof value !== 'object' || value === null) {
    throw new AnalysisResponseShapeError(`${path} was not an object`)
  }
  const event = value as Record<string, unknown>
  if (typeof event.building_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.building_id was not a number`)
  }
  if (typeof event.world_time_ms !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.world_time_ms was not a number`)
  }
}

function assertAnalysisTrainingEvent(
  value: unknown,
  path: string,
): asserts value is ApiAnalysisTrainingEvent {
  if (typeof value !== 'object' || value === null) {
    throw new AnalysisResponseShapeError(`${path} was not an object`)
  }
  const event = value as Record<string, unknown>
  if (typeof event.unit_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.unit_id was not a number`)
  }
  if (typeof event.amount !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.amount was not a number`)
  }
  if (typeof event.building_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.building_id was not a number`)
  }
  if (typeof event.world_time_ms !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.world_time_ms was not a number`)
  }
}

function assertAnalysisResearchEvent(
  value: unknown,
  path: string,
): asserts value is ApiAnalysisResearchEvent {
  if (typeof value !== 'object' || value === null) {
    throw new AnalysisResponseShapeError(`${path} was not an object`)
  }
  const event = value as Record<string, unknown>
  if (typeof event.technology_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.technology_id was not a number`)
  }
  if (typeof event.world_time_ms !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.world_time_ms was not a number`)
  }
}

function assertAgeUpCommands(
  value: unknown,
  path: string,
): asserts value is Record<string, number> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new AnalysisResponseShapeError(`${path} was not an object`)
  }
  for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
    if (typeof entry !== 'number') {
      throw new AnalysisResponseShapeError(`${path}.${key} was not a number`)
    }
  }
}

function assertAnalysisDocumentParticipant(
  value: unknown,
  index: number,
): asserts value is ApiAnalysisDocumentParticipant {
  const path = `participants[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new AnalysisResponseShapeError(`${path} was not an object`)
  }
  const participant = value as Record<string, unknown>
  if (typeof participant.profile_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (typeof participant.player_number !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.player_number was not a number`)
  }
  if (typeof participant.civ_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.civ_id was not a number`)
  }
  if (typeof participant.resolved_team_id !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.resolved_team_id was not a number`)
  }
  if (!Array.isArray(participant.builds)) {
    throw new AnalysisResponseShapeError(`${path}.builds was not an array`)
  }
  participant.builds.forEach((event, i) => assertAnalysisBuildEvent(event, `${path}.builds[${i}]`))
  if (!Array.isArray(participant.trainings)) {
    throw new AnalysisResponseShapeError(`${path}.trainings was not an array`)
  }
  participant.trainings.forEach((event, i) =>
    assertAnalysisTrainingEvent(event, `${path}.trainings[${i}]`),
  )
  if (!Array.isArray(participant.researches)) {
    throw new AnalysisResponseShapeError(`${path}.researches was not an array`)
  }
  participant.researches.forEach((event, i) =>
    assertAnalysisResearchEvent(event, `${path}.researches[${i}]`),
  )
  assertAgeUpCommands(participant.age_up_commands, `${path}.age_up_commands`)
  if (typeof participant.villagers_ordered !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.villagers_ordered was not a number`)
  }
  if (typeof participant.actions !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.actions was not a number`)
  }
  if (typeof participant.actions_per_minute !== 'number') {
    throw new AnalysisResponseShapeError(`${path}.actions_per_minute was not a number`)
  }
  if (!isNullableNumber(participant.resigned_at_ms)) {
    throw new AnalysisResponseShapeError(`${path}.resigned_at_ms was not number|null`)
  }
}

export function assertAnalysisDocument(payload: unknown): asserts payload is ApiAnalysisDocument {
  if (typeof payload !== 'object' || payload === null) {
    throw new AnalysisResponseShapeError('document response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (typeof body.schema_version !== 'number') {
    throw new AnalysisResponseShapeError('"schema_version" was not a number')
  }
  if (typeof body.game_id !== 'number') {
    throw new AnalysisResponseShapeError('"game_id" was not a number')
  }
  if (typeof body.point_of_view_profile_id !== 'number') {
    throw new AnalysisResponseShapeError('"point_of_view_profile_id" was not a number')
  }
  if (typeof body.engine !== 'object' || body.engine === null) {
    throw new AnalysisResponseShapeError('"engine" was not an object')
  }
  const engine = body.engine as Record<string, unknown>
  if (typeof engine.name !== 'string') {
    throw new AnalysisResponseShapeError('"engine.name" was not a string')
  }
  if (typeof engine.version !== 'string') {
    throw new AnalysisResponseShapeError('"engine.version" was not a string')
  }
  if (typeof body.source_recording !== 'object' || body.source_recording === null) {
    throw new AnalysisResponseShapeError('"source_recording" was not an object')
  }
  if (typeof body.extracted_at !== 'string') {
    throw new AnalysisResponseShapeError('"extracted_at" was not a string')
  }
  if (!Array.isArray(body.participants)) {
    throw new AnalysisResponseShapeError('"participants" was not an array')
  }
  body.participants.forEach((participant, index) =>
    assertAnalysisDocumentParticipant(participant, index),
  )
}

/** `GET /api/matches/{game_id}/analysis` (`contracts/http-api.md`'s Analysis table, FR-030) — the
 * published document, read only while `analysis.state === 'published'` (`AnalysisContainer.tsx`'s
 * own `enabled` gate). `404` in every other state, which this function never calls into (the
 * caller checks `state` first). */
export function fetchAnalysisDocument(gameId: number): Promise<ApiAnalysisDocument> {
  return api.get<unknown>(`/api/matches/${gameId}/analysis`).then((payload) => {
    assertAnalysisDocument(payload)
    return payload
  })
}

export function analysisDocumentQueryOptions(gameId: number) {
  return queryOptions({
    queryKey: ['matches', 'detail', gameId, 'analysis-document'] as const,
    queryFn: () => fetchAnalysisDocument(gameId),
    enabled: gameId > 0,
  })
}

// --- POST /api/analyze (FR-030, FR-035, FR-041) -------------------------------------------------

/**
 * `POST /api/analyze` (`contracts/http-api.md`'s Analysis table) — the one action behind "Request
 * analysis" (`absent`), "Recompute" (`published`, `stale: true`) and "Try requesting analysis"
 * (`refused`): the identical call in every case (`analysis-timeline.md` §3.4). Body carries
 * `game_id`, matching that table's own `{"game_id": ...}`.
 *
 * `AnalysisContainer.tsx` never awaits this promise to decide what to render next
 * (`analysis-timeline.md` §5: "does not wait on its own `POST /api/analyze` response... relying on
 * the very next poll... to read the outcome") — it is fired and its resolution (or rejection, for
 * a rate limit or a cap refusal) is read back only through the next `GET /api/matches/{game_id}`
 * poll, never through this function's own return value. This export still resolves the parsed
 * summary rather than `void`, so a caller that *does* want it (a future retry banner, a test) can
 * read it without a second validated shape existing elsewhere.
 */
export function requestAnalysis(gameId: number): Promise<ApiAnalysisSummary> {
  return api.post<unknown>('/api/analyze', { game_id: gameId }).then((payload) => {
    assertAnalysisSummary(payload)
    return payload
  })
}
