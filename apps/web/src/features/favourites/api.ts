import { queryOptions } from '@tanstack/react-query'
import { api } from '../../lib/api'

// `apps/api/.../routers/favourites.py` (T346) — `GET /api/favourites`,
// `PUT`/`DELETE /api/favourites/{profile_id}` (`contracts/http-api.md`'s Favourites table). Every
// field name here is verbatim what that router puts on the wire, snake_case, the same convention
// `features/players/api.ts` and `features/search/api.ts` follow (T037a: "a type that describes
// the wire is a comment the compiler cannot verify"). The mapping to `FavouriteEntryData`'s
// camelCase shape (packages/design-system) happens once, in `mappers.ts`.

export interface ApiFavouriteRatingSnapshot {
  leaderboard_id: number
  /** Named by the API (`routers/favourites.py`'s `_favourite_ratings`, mirroring
   * `routers/players.py`'s `_profile_ratings`), never looked up here — same rule
   * `features/players/api.ts`'s identical field documents. */
  leaderboard_name: string
  rating: number
  rank: number | null
  wins: number
  losses: number
  streak: number | null
  highest_rating: number | null
  captured_at: string
}

export interface ApiFavouriteEntry {
  profile_id: number
  /** `null` only when the favourited profile itself has vanished from `aoe_profiles`
   * (`routers/favourites.py`'s `list_favourites`: `profile.alias if profile is not None else
   * None`) — nothing in this codebase deletes an `aoe_profiles` row today, so this is a
   * defensive nullable rather than an expected case; `mappers.ts` still renders the row rather
   * than dropping it, so the caller's own bookmark and its remove control stay reachable. */
  alias: string | null
  country: string | null
  /** FR-014's "current standing" — one snapshot per leaderboard this player has ever played, the
   * identical shape and derivation `features/players/api.ts`'s `ApiPlayerRatingSnapshot` carries
   * for `GET /api/players/{profile_id}`. Leaderboards never played are absent, not
   * present-and-empty (same rule as that module). */
  ratings: ApiFavouriteRatingSnapshot[]
}

export interface FavouritesResponse {
  favourites: ApiFavouriteEntry[]
}

/** Thrown by `assertFavouritesResponse` when `GET /api/favourites`'s body does not match the shape
 * this module declares — mirrors `PlayerProfileResponseShapeError`
 * (`features/players/api.ts`) and `lib/api.ts`'s `ApiResponseShapeError` (T037a). */
export class FavouritesResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/favourites: ${detail}`)
    this.name = 'FavouritesResponseShapeError'
  }
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function assertFavouriteRatingSnapshot(
  value: unknown,
  entryIndex: number,
  index: number,
): asserts value is ApiFavouriteRatingSnapshot {
  const path = `favourites[${entryIndex}].ratings[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new FavouritesResponseShapeError(`${path} was not an object`)
  }
  const snapshot = value as Record<string, unknown>
  if (typeof snapshot.leaderboard_id !== 'number') {
    throw new FavouritesResponseShapeError(`${path}.leaderboard_id was not a number`)
  }
  if (typeof snapshot.leaderboard_name !== 'string') {
    throw new FavouritesResponseShapeError(`${path}.leaderboard_name was not a string`)
  }
  if (typeof snapshot.rating !== 'number') {
    throw new FavouritesResponseShapeError(`${path}.rating was not a number`)
  }
  if (!isNullableNumber(snapshot.rank)) {
    throw new FavouritesResponseShapeError(`${path}.rank was not number|null`)
  }
  if (typeof snapshot.wins !== 'number') {
    throw new FavouritesResponseShapeError(`${path}.wins was not a number`)
  }
  if (typeof snapshot.losses !== 'number') {
    throw new FavouritesResponseShapeError(`${path}.losses was not a number`)
  }
  if (!isNullableNumber(snapshot.streak)) {
    throw new FavouritesResponseShapeError(`${path}.streak was not number|null`)
  }
  if (!isNullableNumber(snapshot.highest_rating)) {
    throw new FavouritesResponseShapeError(`${path}.highest_rating was not number|null`)
  }
  if (typeof snapshot.captured_at !== 'string') {
    throw new FavouritesResponseShapeError(`${path}.captured_at was not a string`)
  }
}

function assertFavouriteEntry(value: unknown, index: number): asserts value is ApiFavouriteEntry {
  const path = `favourites[${index}]`
  if (typeof value !== 'object' || value === null) {
    throw new FavouritesResponseShapeError(`${path} was not an object`)
  }
  const entry = value as Record<string, unknown>
  if (typeof entry.profile_id !== 'number') {
    throw new FavouritesResponseShapeError(`${path}.profile_id was not a number`)
  }
  if (!isNullableString(entry.alias)) {
    throw new FavouritesResponseShapeError(`${path}.alias was not string|null`)
  }
  if (!isNullableString(entry.country)) {
    throw new FavouritesResponseShapeError(`${path}.country was not string|null`)
  }
  if (!Array.isArray(entry.ratings)) {
    throw new FavouritesResponseShapeError(`${path}.ratings was not an array`)
  }
  entry.ratings.forEach((snapshot, snapshotIndex) =>
    assertFavouriteRatingSnapshot(snapshot, index, snapshotIndex),
  )
}

/** Validates `payload` against `FavouritesResponse` and narrows to it, or throws
 * `FavouritesResponseShapeError` — loudly, not a silently-substituted default (T037a's rule).
 * `fetchFavourites` is the one caller. */
export function assertFavouritesResponse(payload: unknown): asserts payload is FavouritesResponse {
  if (typeof payload !== 'object' || payload === null) {
    throw new FavouritesResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (!Array.isArray(body.favourites)) {
    throw new FavouritesResponseShapeError('"favourites" was not an array')
  }
  body.favourites.forEach((entry, index) => assertFavouriteEntry(entry, index))
}

/** FR-014, FR-015: the caller's own favourites, never another user's — `routers/favourites.py`'s
 * own `_require_session` answers `401 sign_in_required` (not `not_authenticated`) when signed
 * out, distinct from every other route this client calls (that router's own module docstring). */
export function fetchFavourites(): Promise<FavouritesResponse> {
  return api.get<unknown>('/api/favourites').then((payload) => {
    assertFavouritesResponse(payload)
    return payload
  })
}

export const favouritesQueryOptions = queryOptions({
  queryKey: ['favourites'] as const,
  queryFn: fetchFavourites,
})

// --- PUT / DELETE /api/favourites/{profile_id} (FR-013, FR-016) -------------------------------

export interface FavouriteMutationResult {
  profile_id: number
  favourited: boolean
}

/** Thrown when a `PUT`/`DELETE` response does not match the shape `routers/favourites.py`'s
 * `add_favourite` / `remove_favourite` document (T037a's rule, mirrored from every other
 * `assert*` in this feature). */
export class FavouriteMutationResponseShapeError extends Error {
  constructor(detail: string) {
    super(`Unexpected response shape from /api/favourites/{profile_id}: ${detail}`)
    this.name = 'FavouriteMutationResponseShapeError'
  }
}

function assertFavouriteMutationResult(
  payload: unknown,
): asserts payload is FavouriteMutationResult {
  if (typeof payload !== 'object' || payload === null) {
    throw new FavouriteMutationResponseShapeError('response body was not an object')
  }
  const body = payload as Record<string, unknown>
  if (typeof body.profile_id !== 'number') {
    throw new FavouriteMutationResponseShapeError('"profile_id" was not a number')
  }
  if (typeof body.favourited !== 'boolean') {
    throw new FavouriteMutationResponseShapeError('"favourited" was not a boolean')
  }
}

/** FR-013: idempotent — marking the same profile twice is one row and two `200`s
 * (`routers/favourites.py`'s own docstring). FR-016: refused with `favourites_limit_reached`
 * (`ApiRequestError`, `409`) at the configured bound for a genuinely new favourite. */
export function addFavourite(profileId: number): Promise<FavouriteMutationResult> {
  return api.put<unknown>(`/api/favourites/${profileId}`).then((payload) => {
    assertFavouriteMutationResult(payload)
    return payload
  })
}

/** FR-013: idempotent — unmarking an already-unmarked profile still answers `200`. */
export function removeFavourite(profileId: number): Promise<FavouriteMutationResult> {
  return api.delete<unknown>(`/api/favourites/${profileId}`).then((payload) => {
    assertFavouriteMutationResult(payload)
    return payload
  })
}
