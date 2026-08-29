// `apps/api/.../routers/replays.py`'s `_match_page_redirect_for_download_failure` (2026-08-29):
// a failed `GET /api/matches/{game_id}/replay/{profile_id}`, reached by the same-tab navigation
// `api.ts`'s `triggerReplayPointOfViewDownload` triggers (`replay-availability.md` §10), answers a
// `303` back to this exact match page rather than a raw JSON body — the SPA reloads, and these
// three query parameters are how the server hands the failure back to it: `replay_error` (the
// identical `code` an API caller would have read from the JSON envelope), `replay_error_profile_id`
// (which row it belongs to — this route is reachable for any participant's point of view, never
// only the caller's own), and `replay_error_retry_after` (present only when the error carried one,
// `rate_limited`'s own `detail.retry_after`).
//
// Read once, on load, and cleared immediately after (`MatchDetailContainer.tsx`'s own effect) so a
// plain refresh of the match page does not resurrect a stale alert — `replay-availability.md` §5's
// own "distinct for exactly one page load" rule, now genuinely reachable in production instead of
// only in Storybook.

const REPLAY_ERROR_PARAM = 'replay_error'
const REPLAY_ERROR_PROFILE_ID_PARAM = 'replay_error_profile_id'
const REPLAY_ERROR_RETRY_AFTER_PARAM = 'replay_error_retry_after'

export interface ReplayDownloadFailure {
  /** `contracts/http-api.md`'s stable `code` — `expired_since_page_load`, `rate_limited`, or any
   * other failure this route can raise (`never_recorded`, `expired`, `not_found`), all folded into
   * the same generic "could not start" alert by `availability.ts`'s own mapping. */
  code: string
  /** `ReplayAvailabilityRowData.id` — `String(profile_id)`, matching `availability.ts`'s own key
   * (`toReplayAvailabilityRows`), never rebuilt or re-derived from anything else on this page. */
  profileId: string
  /** Only present for `rate_limited`; the exact seconds the server's own `detail.retry_after`
   * carried, never rounded or invented (`replay-availability.md` §5). */
  retryAfterSeconds?: number
}

/** `location.search` (leading `?` or empty) to the failure it carries, or `null` for an ordinary
 * visit — every other query string this route answers with. `replay_error_profile_id` is required
 * alongside `replay_error`: a code with nothing to attach it to cannot address a row. */
export function parseReplayDownloadFailure(search: string): ReplayDownloadFailure | null {
  const params = new URLSearchParams(search)
  const code = params.get(REPLAY_ERROR_PARAM)
  const profileId = params.get(REPLAY_ERROR_PROFILE_ID_PARAM)
  if (!code || !profileId) {
    return null
  }
  const retryAfterRaw = params.get(REPLAY_ERROR_RETRY_AFTER_PARAM)
  const retryAfterSeconds =
    retryAfterRaw !== null && /^\d+$/.test(retryAfterRaw) ? Number(retryAfterRaw) : undefined
  return { code, profileId, retryAfterSeconds }
}

/** `search` with this module's own three parameters removed, everything else untouched —
 * `MatchDetailContainer.tsx`'s own effect writes the result back with `history.replaceState`
 * rather than a router navigation, since clearing them must not itself trigger a second render of
 * `matchQuery` or add a history entry a user's "back" button would then have to skip past. */
export function searchWithoutReplayDownloadFailure(search: string): string {
  const params = new URLSearchParams(search)
  params.delete(REPLAY_ERROR_PARAM)
  params.delete(REPLAY_ERROR_PROFILE_ID_PARAM)
  params.delete(REPLAY_ERROR_RETRY_AFTER_PARAM)
  const remaining = params.toString()
  return remaining ? `?${remaining}` : ''
}
