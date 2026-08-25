import { api } from '../../lib/api'

// `apps/api/.../routers/players.py` (T319), `GET /api/players/search?q=` — every field name here
// is verbatim what that router puts in the response body (its own `search_for_players`),
// snake_case, the same convention `features/matches/api.ts` and `features/profile/api.ts` follow
// (T037a: "a type that describes the wire is a comment the compiler cannot verify"). The mapping
// to `PlayerSearchResultData`'s camelCase props (packages/design-system) happens once, in
// `mappers.ts`.

export interface ApiPlayerSearchResult {
  profile_id: number
  alias: string
  country: string | null
  /** `null` for a result answered by FR-004d's local fallback: `aoe_profiles` has no
   * games-played column (`contracts/http-api.md`). */
  games_played: number | null
  clan: string | null
  /** The source's own, unverified Steam claim (`contracts/http-api.md`'s sixth search field,
   * `contracts/providers.md`'s `unverified_steam_id`, constitution IX 3.0.0). `null` on the
   * degraded fallback (FR-004d), which has no such claim to carry — never read as "no Steam
   * account" (`contracts/http-api.md`).
   *
   * Optional here, not just nullable: `GET /api/players/search` does not yet put this field on
   * the wire (T398 wires it; this feature's design-system spec, T399, ships ahead of it per
   * tasks.md). A response missing the key entirely is treated the same as `null` by
   * `assertPlayerSearchResult` and `mappers.ts`'s `toPlayerSearchResult`, so this module needs no
   * further change once T398 lands and starts sending the key on every result. */
  unverified_steam_id?: string | null
}

export interface PlayerSearchResponse {
  results: ApiPlayerSearchResult[]
  /** FR-003: never collapsed with `results.length` — a source outage that also finds nothing
   * locally still answers `degraded: true`, distinct from an ordinary "no match" (`degraded:
   * false`). */
  degraded: boolean
  reason: string | null
}

/** Thrown by `assertPlayerSearchResponse` when `GET /api/players/search`'s body does not match
 * the shape this module declares — mirrors `MatchesResponseShapeError`
 * (`features/matches/api.ts`) and `lib/api.ts`'s `ApiResponseShapeError` (T037a). */
export class PlayerSearchResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/players/search: ${detail}`)
    this.name = 'PlayerSearchResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function assertPlayerSearchResult(
  value: unknown,
  index: number,
): asserts value is ApiPlayerSearchResult {
  const path = `results[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new PlayerSearchResponseShapeError(`${path} was not an object`)
  }
  const result = value as Record<string, unknown>
  if (typeof result.profile_id !== 'number') {
    throw new PlayerSearchResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (typeof result.alias !== 'string') {
    throw new PlayerSearchResponseShapeError(`${path}.alias was not a string`)
  }
  if (!isNullableString(result.country)) {
    throw new PlayerSearchResponseShapeError(`${path}.country was not string|null`)
  }
  if (!isNullableNumber(result.games_played)) {
    throw new PlayerSearchResponseShapeError(`${path}.games_played was not number|null`)
  }
  if (!isNullableString(result.clan)) {
    throw new PlayerSearchResponseShapeError(`${path}.clan was not string|null`)
  }
  // Optional key (see `ApiPlayerSearchResult.unverified_steam_id`'s own docstring): absent is
  // accepted so this assertion does not break on a response from before T398 wires the field.
  // Present, it must still be string|null — a wrongly-shaped value is still a shape fault.
  if ('unverified_steam_id' in result && !isNullableString(result.unverified_steam_id)) {
    throw new PlayerSearchResponseShapeError(`${path}.unverified_steam_id was not string|null`)
  }
}

/** Validates `payload` against `PlayerSearchResponse` and narrows to it, or throws
 * `PlayerSearchResponseShapeError` — loudly, not a silently-substituted default (T037a's rule).
 * `searchPlayers` is the one caller. */
export function assertPlayerSearchResponse(
  payload: unknown,
): asserts payload is PlayerSearchResponse {
  if (typeof payload !== 'object' || payload === null) {
    throw new PlayerSearchResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (!Array.isArray(body.results)) {
    throw new PlayerSearchResponseShapeError('"results" was not an array')
  }
  body.results.forEach((result, index) => assertPlayerSearchResult(result, index))
  if (typeof body.degraded !== 'boolean') {
    throw new PlayerSearchResponseShapeError('"degraded" was not a boolean')
  }
  if (!isNullableString(body.reason)) {
    throw new PlayerSearchResponseShapeError('"reason" was not string|null')
  }
}

/** FR-001: find a player by display name, with no numeric identifier known. Not wired through
 * TanStack Query's `useQuery` — `SearchBox` (packages/design-system) drives its own debounce and
 * dispatches one `onSearch` per settled query, so `SearchContainer` (T322) calls this directly and
 * tracks in-flight state itself, the same way `DashboardContainer.tsx`'s mutations do. */
export function searchPlayers(query: string): Promise<PlayerSearchResponse> {
  const params = new URLSearchParams({ q: query })
  return api.get<unknown>(`/api/players/search?${params.toString()}`).then((payload) => {
    assertPlayerSearchResponse(payload)
    return payload
  })
}
