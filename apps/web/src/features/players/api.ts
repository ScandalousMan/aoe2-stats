import { queryOptions } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { assertMatchesResponse } from '../matches/api'
import type { MatchesResponse } from '../matches/api'

// `apps/api/.../routers/players.py` (T319), `GET /api/players/{profile_id}` — every field name
// here is verbatim what that router's `get_player_profile` puts in the response body,
// snake_case, the same convention `features/matches/api.ts` and `features/search/api.ts` follow
// (T037a: "a type that describes the wire is a comment the compiler cannot verify"). The mapping
// to `ProfileSummary`'s camelCase props (packages/design-system) happens once, in `mappers.ts`.
//
// FR-008a property 1: this is "any profile", not "mine" — `routers/profiles.py`'s
// `/api/profiles/*` (`features/profile/api.ts`) stays the owner-scoped route for the caller's own
// linked profiles; this module reads a third party's the same way, by `profile_id`.

export interface ApiPlayerRatingSnapshot {
  leaderboard_id: number
  /** Named by the API (`routers/leaderboards.py`), never looked up here — same rule
   * `features/profile/api.ts`'s `ApiRatingSnapshot.leaderboard_name` already documents. */
  leaderboard_name: string
  rating: number
  /** Relic's own convention, passed through unmodified: `-1` means "not enough games for a rank
   * yet", not "rank zero" (`features/profile/api.ts`'s identical field). `mappers.ts` reuses
   * `formatRank` from `features/profile/format.ts` rather than re-deriving this. */
  rank: number | null
  wins: number
  losses: number
  streak: number | null
  highest_rating: number | null
  captured_at: string
}

export interface ApiPlayerProfile {
  profile_id: number
  alias: string
  country: string | null
  /** T421, T426; `contracts/http-api.md`: read straight off `aoe_profiles.avatar_hash`, never
   * fetched — a hash, never a URL (`mappers.ts`'s `toViewedProfile` passes it straight through,
   * `PlayerAvatar` builds the CDN URL). `null` is the ordinary case for a profile never seen in a
   * companion response, not an error (`routers/players.py`'s own note). */
  avatar_hash: string | null
  /** `null` only for a profile this service has observed through a match but never through its
   * own alias-refresh path (`routers/players.py`'s module docstring). `mappers.ts` renders this as
   * `ProfileSummary`'s `AliasFreshnessNote` when present (003 spec §11.1.4). */
  alias_observed_at: string | null
  /** Leaderboards this player has never played are absent, not present-and-empty — same rule
   * `features/profile/mappers.ts`'s `toRatingEntries` already documents for the caller's own
   * profile (FR-008, US1 scenario 5: a never-ranked player is a valid profile, not an error). */
  ratings: ApiPlayerRatingSnapshot[]
}

/** Thrown by `assertPlayerProfileResponse` when `GET /api/players/{profile_id}`'s body does not
 * match the shape this module declares — mirrors `MatchesResponseShapeError`
 * (`features/matches/api.ts`) and `lib/api.ts`'s `ApiResponseShapeError` (T037a). */
export class PlayerProfileResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/players/{profile_id}: ${detail}`)
    this.name = 'PlayerProfileResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function assertPlayerRatingSnapshot(
  value: unknown,
  index: number,
): asserts value is ApiPlayerRatingSnapshot {
  const path = `ratings[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new PlayerProfileResponseShapeError(`${path} was not an object`)
  }
  const snapshot = value as Record<string, unknown>
  if (typeof snapshot.leaderboard_id !== 'number') {
    throw new PlayerProfileResponseShapeError(`${path}.leaderboard_id was not a number`)
  }
  if (typeof snapshot.leaderboard_name !== 'string') {
    throw new PlayerProfileResponseShapeError(`${path}.leaderboard_name was not a string`)
  }
  if (typeof snapshot.rating !== 'number') {
    throw new PlayerProfileResponseShapeError(`${path}.rating was not a number`)
  }
  if (!isNullableNumber(snapshot.rank)) {
    throw new PlayerProfileResponseShapeError(`${path}.rank was not number|null`)
  }
  if (typeof snapshot.wins !== 'number') {
    throw new PlayerProfileResponseShapeError(`${path}.wins was not a number`)
  }
  if (typeof snapshot.losses !== 'number') {
    throw new PlayerProfileResponseShapeError(`${path}.losses was not a number`)
  }
  if (!isNullableNumber(snapshot.streak)) {
    throw new PlayerProfileResponseShapeError(`${path}.streak was not number|null`)
  }
  if (!isNullableNumber(snapshot.highest_rating)) {
    throw new PlayerProfileResponseShapeError(`${path}.highest_rating was not number|null`)
  }
  if (typeof snapshot.captured_at !== 'string') {
    throw new PlayerProfileResponseShapeError(`${path}.captured_at was not a string`)
  }
}

/** Validates `payload` against `ApiPlayerProfile` and narrows to it, or throws
 * `PlayerProfileResponseShapeError` — loudly, not a silently-substituted default (T037a's rule).
 * `fetchPlayerProfile` is the one caller. */
export function assertPlayerProfileResponse(payload: unknown): asserts payload is ApiPlayerProfile {
  if (typeof payload !== 'object' || payload === null) {
    throw new PlayerProfileResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (typeof body.profile_id !== 'number') {
    throw new PlayerProfileResponseShapeError('"profile_id" was not a number')
  }
  if (typeof body.alias !== 'string') {
    throw new PlayerProfileResponseShapeError('"alias" was not a string')
  }
  if (!isNullableString(body.country)) {
    throw new PlayerProfileResponseShapeError('"country" was not string|null')
  }
  if (!isNullableString(body.avatar_hash)) {
    throw new PlayerProfileResponseShapeError('"avatar_hash" was not string|null')
  }
  if (!isNullableString(body.alias_observed_at)) {
    throw new PlayerProfileResponseShapeError('"alias_observed_at" was not string|null')
  }
  if (!Array.isArray(body.ratings)) {
    throw new PlayerProfileResponseShapeError('"ratings" was not an array')
  }
  body.ratings.forEach((snapshot, index) => assertPlayerRatingSnapshot(snapshot, index))
}

/** FR-006, FR-008a property 1: any profile this service has observed — `404` (via `ApiRequestError`,
 * code `"not_found"`) only for a `profile_id` never observed at all; `200` with empty `ratings` for
 * a never-ranked player (US1 scenario 5). */
export function fetchPlayerProfile(profileId: number): Promise<ApiPlayerProfile> {
  return api.get<unknown>(`/api/players/${profileId}`).then((payload) => {
    assertPlayerProfileResponse(payload)
    return payload
  })
}

/** Distinct query key per `profileId`, the same discipline `features/matches/api.ts`'s
 * `matchDetailQueryOptions` applies — never folded into `meQueryOptions` or `profilesQueryOptions`
 * (`features/profile/api.ts`), which answer only for the caller's own linked profiles. */
export function playerProfileQueryOptions(profileId: number) {
  return queryOptions({
    queryKey: ['players', profileId] as const,
    queryFn: () => fetchPlayerProfile(profileId),
    enabled: profileId > 0,
  })
}

// --- GET /api/players/{profile_id}/matches (T328, T331) ---------------------------------------
//
// `apps/api/.../routers/players.py`'s `get_player_match_history`: "the same row shape `GET
// /api/matches` already returns" (FR-008, that router's own docstring) — `match_row_json` is one
// function imported by both routers, so this module reuses `features/matches/api.ts`'s
// `MatchesResponse`/`ApiMatchListRow`/`assertMatchesResponse` rather than declaring a second,
// necessarily-identical copy that could drift from the one the wire actually never lets drift.

export interface FetchPlayerMatchesParams {
  profileId: number
  cursor?: string | null
}

/** FR-007, FR-008a property 1: any player's matches, newest first — `404` only for a `profile_id`
 * this service has never observed at all (the same `not_found` `fetchPlayerProfile` above
 * documents); a player with zero matches answers `200` with an empty `matches` array, never an
 * error (`routers/players.py`'s own "not an error" case). */
export function fetchPlayerMatches({
  profileId,
  cursor,
}: FetchPlayerMatchesParams): Promise<MatchesResponse> {
  const params = new URLSearchParams()
  if (cursor) {
    params.set('cursor', cursor)
  }
  const query = params.toString()
  return api
    .get<unknown>(`/api/players/${profileId}/matches${query ? `?${query}` : ''}`)
    .then((payload) => {
      assertMatchesResponse(payload)
      return payload
    })
}

/** Distinct query key from `matchesQueryOptions` (`features/matches/api.ts`) even though the
 * response shape is identical — the two routes answer for a different subject (the caller's own
 * profile vs. any `profile_id`) and must never share a cache entry. */
export function playerMatchesQueryOptions(profileId: number, cursor: string | null = null) {
  return queryOptions({
    queryKey: ['players', profileId, 'matches', cursor] as const,
    queryFn: () => fetchPlayerMatches({ profileId, cursor }),
    enabled: profileId > 0,
  })
}
