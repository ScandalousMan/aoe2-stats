import { queryOptions } from '@tanstack/react-query'
import { api } from '../../lib/api'

// `apps/api/.../routers/profiles.py` (T031) and `routers/privacy.py` (T032). Every field name
// here is verbatim what those handlers put in the response body — snake_case, because neither
// router builds a Pydantic response model with a camelCase alias generator, it hand-assembles a
// `dict[str, Any]`. `lib/api.ts`'s `MeResponse` follows the same convention (T037a: it used to
// declare a camelCase shape — `profileId`, `isPrimary`, `ingestConsentGranted` — that `GET
// /api/me` had never actually sent; both are now snake_case and `assertMeResponse` checks it at
// the boundary). The mapping to `ProfileSummary`'s camelCase props happens once, in `mappers.ts`.

export interface ApiRatingSnapshot {
  leaderboard_id: number
  /** Named by the API (`routers/profiles.py`, T033a), not looked up here — Relic's own
   * `getPersonalStat` returns only `leaderboard_id`, never a name, so the backend's
   * `leaderboards.py` is the one hand-maintained copy of this mapping (`docs/data-sources.md`
   * §1). The front end no longer keeps a duplicate. */
  leaderboard_name: string
  rating: number
  /** Relic's own convention, passed through unmodified from `getPersonalStat`
   * (`docs/data-sources.md` §1): `-1` means "not enough games for a rank yet", not "rank zero".
   * `format.ts`'s `formatRank` is where that gets turned into "no rank" rather than the row
   * itself deciding it. */
  rank: number | null
  wins: number
  losses: number
  streak: number | null
  highest_rating: number | null
  captured_at: string
}

export interface ApiProfile {
  profile_id: number
  alias: string
  country: string | null
  is_primary: boolean
  linked_at: string
  ratings: ApiRatingSnapshot[]
}

export interface ProfilesResponse {
  profiles: ApiProfile[]
}

export function fetchProfiles(): Promise<ProfilesResponse> {
  return api.get<ProfilesResponse>('/api/profiles')
}

/** Distinct query key from `meQueryOptions` (`lib/api.ts`): `GET /api/profiles` is the one call
 * that carries ratings, and it is fetched once here rather than folded into the session bootstrap
 * that every route pays for in `__root.tsx`'s `beforeLoad` (T017). */
export const profilesQueryOptions = queryOptions({
  queryKey: ['profiles'] as const,
  queryFn: fetchProfiles,
  staleTime: 30_000,
})

export interface SetPrimaryResponse {
  profile_id: number
  is_primary: boolean
}

/** FR-043. */
export function setPrimaryProfile(profileId: number): Promise<SetPrimaryResponse> {
  return api.post<SetPrimaryResponse>(`/api/profiles/${profileId}/primary`)
}

export interface ArchivedReplaysPreview {
  retained: boolean
  count: number
  message: string
}

export interface UnlinkPreviewResponse {
  confirmed: false
  archived_replays: ArchivedReplaysPreview
}

export interface UnlinkConfirmResponse {
  confirmed: true
  unlinked_at: string
  archived_replays: ArchivedReplaysPreview
}

/** FR-004's preview call — no `?confirm=true` — states the consequence for archived replays
 * without unlinking anything yet. */
export function previewUnlink(profileId: number): Promise<UnlinkPreviewResponse> {
  return api.delete<UnlinkPreviewResponse>(`/api/profiles/${profileId}`)
}

/** FR-004's confirming call, only ever issued after the preview has been shown and the user has
 * pressed the dialog's own confirm action — never in the same step as the preview. */
export function confirmUnlink(profileId: number): Promise<UnlinkConfirmResponse> {
  return api.delete<UnlinkConfirmResponse>(`/api/profiles/${profileId}?confirm=true`)
}

export interface ArchivalObjectionResponse {
  archival_objected: boolean
  archival_objected_at: string | null
}

/** FR-035, `POST /api/privacy/archival-objection` (renamed with an inverted meaning from
 * `POST /api/privacy/consent` by T405, constitution IX 4.0.0 — there is no longer a grant to
 * record). `{"objected": true}` objects, stopping future capture; `{"objected": false}` resumes
 * archival by clearing the objection, and is a no-op, not an error, when there was never one to
 * clear. */
export function setArchivalObjection(objected: boolean): Promise<ArchivalObjectionResponse> {
  return api.post<ArchivalObjectionResponse>('/api/privacy/archival-objection', { objected })
}
