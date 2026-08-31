import { queryOptions } from '@tanstack/react-query'
import { api } from '../../lib/api'

// `apps/api/.../routers/matches.py` (T070), `GET /api/matches` — every field name here is
// verbatim what that router puts in the response body (its own `_match_row_json`), snake_case,
// the same convention `features/profile/api.ts` documents for `profiles.py` and `privacy.py`
// (T037a: "a type that describes the wire is a comment the compiler cannot verify"). The mapping
// to `MatchRowData`'s camelCase props (packages/design-system) happens once, in `mappers.ts`.

export interface ApiOpponent {
  profile_id: number
  alias: string | null
  civ_id: number | null
  /** `matches.py`'s `_opponent_json` (T070c) — `civilisation_name` computed server-side, same
   * shape `civilisation_name` below carries for the caller's own row. Not yet read by any mapper:
   * `MatchRowOpponent` (packages/design-system) shows no civ for an opponent today. */
  civ_name: string | null
}

/** One entry of `GET /api/matches`'s `participants[]` (`contracts/http-api.md`, T425) — match
 * detail's participant shape **minus `replay`**, which is detail-only (FR-023). Never reuse
 * `ApiMatchParticipant`/`assertMatchParticipant` below for this shape: that one calls
 * `assertReplayAvailability` unconditionally and would reject every list row. */
export interface ApiMatchRowParticipant {
  profile_id: number
  alias: string | null
  /** New on this shape (004): feeds the opponent flag client-side, resolved through
   * `packages/game-assets`. `null` when unknown. */
  country: string | null
  team_id: number | null
  civ_id: number | null
  /** Always present alongside a real `civ_id` (004's own contract rule) — this client never
   * formats a bare id itself. */
  civ_name: string | null
  color_id: number | null
  /** `"win"`, `"loss"`, or `null` — `null` is FR-004's neutral state, never a loss. */
  result: string | null
  rating: number | null
  rating_diff: number | null
}

export interface ApiMatchListRow {
  game_id: number
  started_at: string | null
  completed_at: string
  map_name: string | null
  leaderboard_id: number
  /** `leaderboard_id`'s name, computed server-side (`matches.py`'s `_match_row_json`, T070f) —
   * the same `aoe2stats_api.leaderboards.leaderboard_name` helper `GET /api/profiles` already
   * reads (T033a), never a client-side stand-in table. */
  leaderboard_name: string
  duration_seconds: number | null
  /** The caller's own `civ_id` for this match (`matches.py`'s module docstring: "FR-010 says
   * 'civilisation', meaning the caller's, never an opponent's"). */
  civilisation: number | null
  /** `civilisation`'s name, computed server-side (`matches.py`'s `_match_row_json`, T070c) —
   * `null` only when `civilisation` itself is `null`; otherwise never a bare id, not even for an
   * id `aoe2stats_api.civilizations` does not recognise (it falls back to "Civilisation <id>"
   * there, not here — see `format.ts`'s own note on why this module no longer hand-maps one). */
  civilisation_name: string | null
  /** The caller's own result — `"win"` or `"loss"` when known, `null` for every row this system
   * has not yet enriched (`match_players.result`'s own gap, `discover.py`). Not narrowed further
   * here so `null` and any unrecognised value still type-check (`format.ts`'s `formatOutcome` is
   * where it becomes `MatchRowData`'s `'win' | 'loss' | 'unknown'` union — `null`/unrecognised
   * read as `'unknown'`, never coerced to `'loss'`, per match-history.md §2a). */
  result: string | null
  /** The caller's own absolute rating, post-match (004, `contracts/http-api.md`). `null` whenever
   * `rating_diff` is also `null` — never a stand-in `0`. */
  rating: number | null
  rating_diff: number | null
  /** Which side the caller was on (004) — `null` until T413/T415 have projected this match. */
  team_id: number | null
  /** 1..8, or `null` whenever companion has not supplied one yet (004, FR-003/FR-010's degrade
   * path — a permanent resting state, not a migration in progress). */
  color_id: number | null
  /** Every other participant on a **different team** than the caller's own — `matches.py`'s
   * `_opponents_by_game` excludes the caller's own teammates at the query (T070d), so this never
   * includes anyone from the caller's own side, in a 1v1 or a team match alike. Retained
   * unmodified alongside `participants` below (004's contract: "a sibling, not a replacement") —
   * no mapper reads it any longer now that `MatchRow` renders every side from `participants`
   * (match-history.md §12.3 supersedes §4's single-opponent treatment). */
  opponents: ApiOpponent[]
  /** All participants, the caller included (004, T425) — feeds `MatchRow`'s §12.3 `Participants`
   * field. Always an array, never omitted, even for a row `discover.py` has not enriched yet
   * (every participant then simply carries every optional field `null`). */
  participants: ApiMatchRowParticipant[]
  /** `null` only for a match with no `replay_captures` row yet (module docstring) — every raw
   * `CaptureStatus` value otherwise, unmodified: the four-state collapse is `CaptureStateBadge`'s
   * job (capture-state-badge.md §3), never this client's. */
  capture_status: string | null
  capture_deadline_at: string | null
}

export interface MatchesResponse {
  matches: ApiMatchListRow[]
  next_cursor: string | null
}

/** Thrown by `assertMatchesResponse` when `GET /api/matches`'s body does not match the shape this
 * module declares — mirrors `lib/api.ts`'s `ApiResponseShapeError` (T037a), a network response the
 * compiler can never check on its own. Deliberately not an `ApiRequestError`: it is not one of the
 * API's own documented failure codes. */
export class MatchesResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/matches: ${detail}`)
    this.name = 'MatchesResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function assertOpponent(
  value: unknown,
  index: number,
  rowIndex: number,
): asserts value is ApiOpponent {
  const path = `matches[${rowIndex}].opponents[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new MatchesResponseShapeError(`${path} was not an object`)
  }
  const opponent = value as Record<string, unknown>
  if (typeof opponent.profile_id !== 'number') {
    throw new MatchesResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (!isNullableString(opponent.alias)) {
    throw new MatchesResponseShapeError(`${path}.alias was not string|null`)
  }
  if (!isNullableNumber(opponent.civ_id)) {
    throw new MatchesResponseShapeError(`${path}.civ_id was not number|null`)
  }
  if (!isNullableString(opponent.civ_name)) {
    throw new MatchesResponseShapeError(`${path}.civ_name was not string|null`)
  }
}

function assertMatchRowParticipant(
  value: unknown,
  index: number,
  rowIndex: number,
): asserts value is ApiMatchRowParticipant {
  const path = `matches[${rowIndex}].participants[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new MatchesResponseShapeError(`${path} was not an object`)
  }
  const participant = value as Record<string, unknown>
  if (typeof participant.profile_id !== 'number') {
    throw new MatchesResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (!isNullableString(participant.alias)) {
    throw new MatchesResponseShapeError(`${path}.alias was not string|null`)
  }
  if (!isNullableString(participant.country)) {
    throw new MatchesResponseShapeError(`${path}.country was not string|null`)
  }
  if (!isNullableNumber(participant.team_id)) {
    throw new MatchesResponseShapeError(`${path}.team_id was not number|null`)
  }
  if (!isNullableNumber(participant.civ_id)) {
    throw new MatchesResponseShapeError(`${path}.civ_id was not number|null`)
  }
  if (!isNullableString(participant.civ_name)) {
    throw new MatchesResponseShapeError(`${path}.civ_name was not string|null`)
  }
  if (!isNullableNumber(participant.color_id)) {
    throw new MatchesResponseShapeError(`${path}.color_id was not number|null`)
  }
  if (!isNullableString(participant.result)) {
    throw new MatchesResponseShapeError(`${path}.result was not string|null`)
  }
  if (!isNullableNumber(participant.rating)) {
    throw new MatchesResponseShapeError(`${path}.rating was not number|null`)
  }
  if (!isNullableNumber(participant.rating_diff)) {
    throw new MatchesResponseShapeError(`${path}.rating_diff was not number|null`)
  }
}

function assertMatchListRow(value: unknown, index: number): asserts value is ApiMatchListRow {
  const path = `matches[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new MatchesResponseShapeError(`${path} was not an object`)
  }
  const row = value as Record<string, unknown>
  if (typeof row.game_id !== 'number') {
    throw new MatchesResponseShapeError(`${path}.game_id was not a number`)
  }
  if (!isNullableString(row.started_at)) {
    throw new MatchesResponseShapeError(`${path}.started_at was not string|null`)
  }
  if (typeof row.completed_at !== 'string') {
    throw new MatchesResponseShapeError(`${path}.completed_at was not a string`)
  }
  if (!isNullableString(row.map_name)) {
    throw new MatchesResponseShapeError(`${path}.map_name was not string|null`)
  }
  if (typeof row.leaderboard_id !== 'number') {
    throw new MatchesResponseShapeError(`${path}.leaderboard_id was not a number`)
  }
  if (typeof row.leaderboard_name !== 'string') {
    throw new MatchesResponseShapeError(`${path}.leaderboard_name was not a string`)
  }
  if (!isNullableNumber(row.duration_seconds)) {
    throw new MatchesResponseShapeError(`${path}.duration_seconds was not number|null`)
  }
  if (!isNullableNumber(row.civilisation)) {
    throw new MatchesResponseShapeError(`${path}.civilisation was not number|null`)
  }
  if (!isNullableString(row.civilisation_name)) {
    throw new MatchesResponseShapeError(`${path}.civilisation_name was not string|null`)
  }
  if (!isNullableString(row.result)) {
    throw new MatchesResponseShapeError(`${path}.result was not string|null`)
  }
  if (!isNullableNumber(row.rating_diff)) {
    throw new MatchesResponseShapeError(`${path}.rating_diff was not number|null`)
  }
  if (!isNullableNumber(row.rating)) {
    throw new MatchesResponseShapeError(`${path}.rating was not number|null`)
  }
  if (!isNullableNumber(row.team_id)) {
    throw new MatchesResponseShapeError(`${path}.team_id was not number|null`)
  }
  if (!isNullableNumber(row.color_id)) {
    throw new MatchesResponseShapeError(`${path}.color_id was not number|null`)
  }
  if (!Array.isArray(row.opponents)) {
    throw new MatchesResponseShapeError(`${path}.opponents was not an array`)
  }
  row.opponents.forEach((opponent, opponentIndex) => assertOpponent(opponent, opponentIndex, index))
  if (!Array.isArray(row.participants)) {
    throw new MatchesResponseShapeError(`${path}.participants was not an array`)
  }
  row.participants.forEach((participant, participantIndex) =>
    assertMatchRowParticipant(participant, participantIndex, index),
  )
  if (!isNullableString(row.capture_status)) {
    throw new MatchesResponseShapeError(`${path}.capture_status was not string|null`)
  }
  if (!isNullableString(row.capture_deadline_at)) {
    throw new MatchesResponseShapeError(`${path}.capture_deadline_at was not string|null`)
  }
}

/** Validates `payload` against `MatchesResponse` and narrows to it, or throws
 * `MatchesResponseShapeError` — loudly, not a silently-substituted default (T037a's rule,
 * mirrored from `lib/api.ts`'s `assertMeResponse`). `fetchMatches` is the one caller. */
export function assertMatchesResponse(payload: unknown): asserts payload is MatchesResponse {
  if (typeof payload !== 'object' || payload === null) {
    throw new MatchesResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (!Array.isArray(body.matches)) {
    throw new MatchesResponseShapeError('"matches" was not an array')
  }
  body.matches.forEach((row, index) => assertMatchListRow(row, index))
  if (!isNullableString(body.next_cursor)) {
    throw new MatchesResponseShapeError('"next_cursor" was not string|null')
  }
}

export interface FetchMatchesParams {
  profileId: number
  cursor?: string | null
}

/** `GET /api/matches?profile_id=&cursor=` (`contracts/http-api.md`'s Matches table): newest
 * first, cursor paginated — never `?offset=`, per that router's own module docstring. */
export function fetchMatches({ profileId, cursor }: FetchMatchesParams): Promise<MatchesResponse> {
  const params = new URLSearchParams({ profile_id: String(profileId) })
  if (cursor) {
    params.set('cursor', cursor)
  }
  return api.get<unknown>(`/api/matches?${params.toString()}`).then((payload) => {
    assertMatchesResponse(payload)
    return payload
  })
}

/** One page of `profileId`'s match history. `cursor` is folded into the query key so a later page
 * is its own cache entry — `MatchHistoryContainer` (T075) concatenates pages itself rather than
 * relying on an infinite-query cache shape this feature does not otherwise need. */
export function matchesQueryOptions(profileId: number, cursor: string | null = null) {
  return queryOptions({
    queryKey: ['matches', profileId, cursor] as const,
    queryFn: () => fetchMatches({ profileId, cursor }),
    enabled: profileId > 0,
  })
}

// --- GET /api/matches/{game_id} (T076, T070e) ------------------------------------------------
//
// `apps/api/.../routers/matches.py`'s `_match_detail_json`: every field name here is again
// verbatim off the wire, snake_case, the same convention this module already documents above for
// `GET /api/matches`. `capture_status` / `capture_deadline_at` are the same two fields
// `ApiMatchListRow` carries above — `get_match_detail` (`packages/storage`'s
// `MatchesRepository`) resolves both via the identical `LEFT OUTER JOIN` `list_matches` already
// uses (T070e), so this route and the list route answer with one vocabulary, not two.

/** `matches.py`'s `_replay_json` (T338, FR-023) — one per participant, exactly `contracts/
 * http-api.md`'s "Recorded games, per point of view" shape. `download_path` and
 * `obtainable_until` are `null` for `expired` and `never_recorded` (FR-025's whole point: an
 * unobtainable download must not be renderable as a button that then fails), and
 * `obtainable_until` is `null` in every state today (FR-024, amended 2026-08-29 — the retention
 * window is unresolved) — never invented client-side either way. */
export interface ApiReplayAvailability {
  profile_id: number
  availability: 'archived' | 'obtainable' | 'expired' | 'never_recorded'
  obtainable_until: string | null
  download_path: string | null
}

export interface ApiMatchParticipant {
  profile_id: number
  alias: string | null
  team_id: number | null
  civ_id: number | null
  /** `matches.py`'s `_match_detail_json`, same shape T070c already gave `ApiOpponent.civ_name`
   * and `ApiMatchListRow.civilisation_name` above. */
  civ_name: string | null
  color_id: number | null
  result: string | null
  rating: number | null
  rating_diff: number | null
  /** T338: this participant's own point of view — always present, one per participant (FR-023). */
  replay: ApiReplayAvailability
}

export interface ApiMatchDetail {
  game_id: number
  started_at: string | null
  completed_at: string
  map_name: string | null
  leaderboard_id: number
  /** `leaderboard_id`'s name, computed server-side (`matches.py`'s `_match_detail_json`, T070f) —
   * same field and same helper as `ApiMatchListRow.leaderboard_name` above. */
  leaderboard_name: string
  duration_seconds: number | null
  /** FR-018's "game version" (`matches.py`'s `_match_detail_json`, T327) — `matches.patch`
   * verbatim. There is no id-to-name table for a patch string the way there is for `civ_id` and
   * `leaderboard_id`, so this is never resolved server-side and never subject to the
   * `UnresolvedIdentifier` treatment `civ_name`/`map_name` get (match-history.md §11.1 point 3). */
  patch: string | null
  participants: ApiMatchParticipant[]
  /** `null` only for a match with no `replay_captures` row yet for any of the caller's linked
   * profiles (`matches.py`'s `get_match_detail`, T070e) — every raw `CaptureStatus` value
   * otherwise, unmodified: same shape and same rule as `ApiMatchListRow.capture_status` above. */
  capture_status: string | null
  capture_deadline_at: string | null
}

/** Thrown by `assertMatchDetailResponse` when `GET /api/matches/{game_id}`'s body does not match
 * the shape this module declares — mirrors `MatchesResponseShapeError` above and `lib/api.ts`'s
 * `ApiResponseShapeError` (T037a). */
export class MatchDetailResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/matches/{game_id}: ${detail}`)
    this.name = 'MatchDetailResponseShapeError'
  }
}

const REPLAY_AVAILABILITIES = ['archived', 'obtainable', 'expired', 'never_recorded'] as const

function assertReplayAvailability(
  value: unknown,
  path: string,
): asserts value is ApiReplayAvailability {
  if (typeof value !== 'object' || value === null) {
    throw new MatchDetailResponseShapeError(`${path} was not an object`)
  }
  const replay = value as Record<string, unknown>
  if (typeof replay.profile_id !== 'number') {
    throw new MatchDetailResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (
    typeof replay.availability !== 'string' ||
    !REPLAY_AVAILABILITIES.includes(replay.availability as (typeof REPLAY_AVAILABILITIES)[number])
  ) {
    throw new MatchDetailResponseShapeError(`${path}.availability was not one of the four states`)
  }
  if (!isNullableString(replay.obtainable_until)) {
    throw new MatchDetailResponseShapeError(`${path}.obtainable_until was not string|null`)
  }
  if (!isNullableString(replay.download_path)) {
    throw new MatchDetailResponseShapeError(`${path}.download_path was not string|null`)
  }
}

function assertMatchParticipant(
  value: unknown,
  index: number,
): asserts value is ApiMatchParticipant {
  const path = `participants[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new MatchDetailResponseShapeError(`${path} was not an object`)
  }
  const participant = value as Record<string, unknown>
  if (typeof participant.profile_id !== 'number') {
    throw new MatchDetailResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (!isNullableString(participant.alias)) {
    throw new MatchDetailResponseShapeError(`${path}.alias was not string|null`)
  }
  if (!isNullableNumber(participant.team_id)) {
    throw new MatchDetailResponseShapeError(`${path}.team_id was not number|null`)
  }
  if (!isNullableNumber(participant.civ_id)) {
    throw new MatchDetailResponseShapeError(`${path}.civ_id was not number|null`)
  }
  if (!isNullableString(participant.civ_name)) {
    throw new MatchDetailResponseShapeError(`${path}.civ_name was not string|null`)
  }
  if (!isNullableNumber(participant.color_id)) {
    throw new MatchDetailResponseShapeError(`${path}.color_id was not number|null`)
  }
  if (!isNullableString(participant.result)) {
    throw new MatchDetailResponseShapeError(`${path}.result was not string|null`)
  }
  if (!isNullableNumber(participant.rating)) {
    throw new MatchDetailResponseShapeError(`${path}.rating was not number|null`)
  }
  if (!isNullableNumber(participant.rating_diff)) {
    throw new MatchDetailResponseShapeError(`${path}.rating_diff was not number|null`)
  }
  assertReplayAvailability(participant.replay, `${path}.replay`)
}

/** Validates `payload` against `ApiMatchDetail` and narrows to it, or throws
 * `MatchDetailResponseShapeError` — loudly, not a silently-substituted default (T037a's rule).
 * `fetchMatchDetail` is the one caller. */
export function assertMatchDetailResponse(payload: unknown): asserts payload is ApiMatchDetail {
  if (typeof payload !== 'object' || payload === null) {
    throw new MatchDetailResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (typeof body.game_id !== 'number') {
    throw new MatchDetailResponseShapeError('"game_id" was not a number')
  }
  if (!isNullableString(body.started_at)) {
    throw new MatchDetailResponseShapeError('"started_at" was not string|null')
  }
  if (typeof body.completed_at !== 'string') {
    throw new MatchDetailResponseShapeError('"completed_at" was not a string')
  }
  if (!isNullableString(body.map_name)) {
    throw new MatchDetailResponseShapeError('"map_name" was not string|null')
  }
  if (typeof body.leaderboard_id !== 'number') {
    throw new MatchDetailResponseShapeError('"leaderboard_id" was not a number')
  }
  if (typeof body.leaderboard_name !== 'string') {
    throw new MatchDetailResponseShapeError('"leaderboard_name" was not a string')
  }
  if (!isNullableNumber(body.duration_seconds)) {
    throw new MatchDetailResponseShapeError('"duration_seconds" was not number|null')
  }
  if (!isNullableString(body.patch)) {
    throw new MatchDetailResponseShapeError('"patch" was not string|null')
  }
  if (!Array.isArray(body.participants)) {
    throw new MatchDetailResponseShapeError('"participants" was not an array')
  }
  body.participants.forEach((participant, index) => assertMatchParticipant(participant, index))
  if (!isNullableString(body.capture_status)) {
    throw new MatchDetailResponseShapeError('"capture_status" was not string|null')
  }
  if (!isNullableString(body.capture_deadline_at)) {
    throw new MatchDetailResponseShapeError('"capture_deadline_at" was not string|null')
  }
}

/** `GET /api/matches/{game_id}` (`contracts/http-api.md`'s Matches table) — reachable through any
 * of the caller's linked profiles, not only the primary one (FR-043); the router itself decides
 * that, this client names no `profile_id` at all. */
export function fetchMatchDetail(gameId: number): Promise<ApiMatchDetail> {
  return api.get<unknown>(`/api/matches/${gameId}`).then((payload) => {
    assertMatchDetailResponse(payload)
    return payload
  })
}

export function matchDetailQueryOptions(gameId: number) {
  return queryOptions({
    queryKey: ['matches', 'detail', gameId] as const,
    queryFn: () => fetchMatchDetail(gameId),
    enabled: gameId > 0,
  })
}
