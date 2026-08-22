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

export interface ApiMatchListRow {
  game_id: number
  started_at: string | null
  completed_at: string
  map_name: string | null
  leaderboard_id: number
  duration_seconds: number | null
  /** The caller's own `civ_id` for this match (`matches.py`'s module docstring: "FR-010 says
   * 'civilisation', meaning the caller's, never an opponent's"). */
  civilisation: number | null
  /** `civilisation`'s name, computed server-side (`matches.py`'s `_match_row_json`, T070c) —
   * `null` only when `civilisation` itself is `null`; otherwise never a bare id, not even for an
   * id `aoe2stats_api.civilizations` does not recognise (it falls back to "Civilisation <id>"
   * there, not here — see `format.ts`'s own note on why this module no longer hand-maps one). */
  civilisation_name: string | null
  /** The caller's own result — `"win"` or `"loss"` today; not narrowed further here so an
   * unrecognised value still type-checks (`mappers.ts` is where it is turned into `MatchRowData`'s
   * strict `'win' | 'loss'` union, defensively). */
  result: string | null
  rating_diff: number | null
  /** Every other participant, own team included — `matches.py`'s repository does not filter by
   * team (its own `_opponents_by_game` docstring: "every `match_players` row ... other than
   * `exclude_profile_id`'s own"), so this is not yet restricted to the opposing team alone. See
   * `mappers.ts`'s own note on the team-game gap this leaves. */
  opponents: ApiOpponent[]
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
  if (!Array.isArray(row.opponents)) {
    throw new MatchesResponseShapeError(`${path}.opponents was not an array`)
  }
  row.opponents.forEach((opponent, opponentIndex) => assertOpponent(opponent, opponentIndex, index))
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
