import type { ApiErrorPayload } from '../../lib/api'
import { ApiRequestError } from '../../lib/api'

// `apps/api/.../routers/replays.py` (T071), `GET /api/replays/{game_id}/download` — this module
// never calls it through `lib/api.ts`'s `api` client: that client parses every response as JSON
// (`apiRequest`'s own `response.json()`), which is wrong for an endpoint whose successful answer
// is a bare 302, not a body. This is the one endpoint in the app reached by full-page navigation
// instead.

/** The same-origin path for `GET /api/replays/{gameId}/download` — never a signed bucket URL
 * built here (`replays.py`'s own docstring: "the bucket is never public... never a hand-built
 * bucket URL"). */
export function replayDownloadPath(gameId: number): string {
  return `/api/replays/${gameId}/download`
}

/**
 * Triggers the browser to follow `GET /api/replays/{gameId}/download`'s 302 to a freshly signed
 * URL, in the current tab (`packages/design-system/specs/match-history.md` §9: "`DownloadAction`
 * triggers a same-tab navigation to the signed-URL redirect... not a bare `<a href>` to an
 * unsigned URL — the URL is minted per click").
 *
 * Deliberately a plain top-level navigation (`window.location.assign`), never a `fetch` that
 * reads the redirected response: nothing in this repository configures CORS on the object store
 * (`packages/storage`, out of this feature's reach), so a script-readable `fetch` following that
 * redirect would reject on the browser's own CORS check — misreporting a perfectly good download
 * as failed, never because the download itself failed. A full navigation carries no such
 * requirement; the browser follows the redirect exactly as it would for any other download link.
 * It is also the only path that reaches the download endpoint exactly once per click, so
 * `replay_access_log` (FR-040) gets exactly the one row the click earned, never two from a probe
 * request plus a real one.
 *
 * One consequence of using a full navigation: there is no script-observable signal for success or
 * failure (the endpoint's one failure mode, `not_found`, would otherwise replace the app with its
 * raw JSON body — see `MatchDetailContainer`'s own note on why it only ever renders the
 * `DownloadAction` once it independently knows the capture is `stored`).
 */
export function triggerReplayDownload(gameId: number): void {
  window.location.assign(replayDownloadPath(gameId))
}

/**
 * Triggers `GET /api/matches/{game_id}/replay/{profile_id}` (T337, FR-023) — one download per
 * participant point of view, reached from `ReplayAvailabilityList`'s own `DownloadAction`
 * (`packages/design-system/specs/replay-availability.md` §10: "a real `<button>` triggering a
 * same-tab navigation to the download endpoint... the URL is minted per click, server-side, on
 * that request" — never a claim that FR-029's access-log write happens on every click: it does
 * not, only the `archived` branch writes one, corrected in that spec 2026-08-29). `path` is
 * `matches/api.ts`'s own `ApiReplayAvailability.download_path`, server-minted — never rebuilt
 * client-side, matching every other identifier this feature refuses to derive on its own (module
 * docstring above).
 *
 * The same reasoning `triggerReplayDownload` carries applies twice over here: this single route
 * answers a 302-to-a-signed-URL for `archived` (a *cross-origin* redirect — the bucket has no
 * CORS configured, `packages/storage/src/aoe2stats_storage/objects.py`'s own docstring, so a
 * script-readable `fetch` following it would reject on the browser's own CORS check) and a
 * same-origin streamed body for `obtainable` (FR-027: fetched from the source and streamed
 * straight through, never stored). A plain top-level navigation is the one mechanism that serves
 * both without a second, divergent code path per state.
 *
 * A failure of this same route (any of the four unobtainable codes, or FR-028's rate limit)
 * answers a `303` back to this exact match page instead of a JSON body, for a browser navigation
 * (`routers/replays.py`'s `_match_page_redirect_for_download_failure`) — the browser follows it as
 * an ordinary continuation of this same navigation, and `downloadFailure.ts` is what the reloaded
 * page reads to render `replay-availability.md` §5's row-level alert.
 */
export function triggerReplayPointOfViewDownload(path: string): void {
  window.location.assign(path)
}

// --- POST /api/replays/{game_id}/upload (T080/T081, T084, FR-029..FR-033) -------------------
//
// `packages/design-system/specs/manual-upload.md`'s own header: `UploadControl` branches on the
// endpoint's `code`, never `message`. This module is the one place that speaks the multipart
// request itself (`UploadControlProps.onUpload`'s own note: "the multipart request itself is
// `onUpload`'s job, wired by the route (T084)") — deliberately not routed through `lib/api.ts`'s
// `api.post`, which always `JSON.stringify`s its body and sets `Content-Type: application/json`
// (wrong for a `multipart/form-data` request; the browser must set that header itself, with the
// boundary `FormData` picks). The error envelope is identical either way, so failures still throw
// the same `ApiRequestError` every other route in this app throws, and `stateForFailure`
// (`UploadControl`) reads its `.code` exactly as it reads any other rejection's.

/** The same-origin path for `POST /api/replays/{gameId}/upload`. */
export function uploadReplayPath(gameId: number): string {
  return `/api/replays/${gameId}/upload`
}

/** `routers/replays.py`'s `upload_replay` response body — `CaptureStatus.STORED` /
 * `CaptureSource.MANUAL` verbatim (manual-upload.md §"success"). Not consumed for its own fields
 * today: the caller re-fetches the match detail instead of trusting this body to describe the
 * whole match (`MatchDetailContainer`'s own note), but the shape is typed rather than discarded
 * outright, matching this app's own "never touch `unknown` past the boundary" discipline. */
export interface UploadReplayResult {
  status: string
  source: string
}

/**
 * Multipart `POST /api/replays/{gameId}/upload`. Resolves with the endpoint's body on `200`;
 * rejects with `ApiRequestError` — carrying `.code`, one of `invalid_replay` (422), `not_found`
 * (404) or `already_archived` (409), or `network_error`/`unknown_error` for anything else — which
 * satisfies `UploadControlProps.onUpload`'s contract (`UploadFailure`'s own `code?: string`) with
 * no adapting in between.
 */
export async function uploadReplay(gameId: number, file: File): Promise<UploadReplayResult> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(uploadReplayPath(gameId), {
      method: 'POST',
      // Mirrors `lib/api.ts`'s `apiRequest`: the session cookie is `HttpOnly` + `Secure` +
      // `SameSite=Lax`, attached automatically for a same-origin request.
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      // No `Content-Type` header here — `fetch` derives `multipart/form-data; boundary=...` from
      // the `FormData` body itself; setting it by hand would drop the boundary the server needs
      // to parse the parts.
      body: formData,
    })
  } catch (cause) {
    throw new ApiRequestError(
      0,
      { code: 'network_error', message: 'The request could not be sent.' },
      { cause },
    )
  }

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const envelope = payload as { error?: ApiErrorPayload } | null
    throw new ApiRequestError(
      response.status,
      envelope?.error ?? {
        code: 'unknown_error',
        message: response.statusText || 'Upload failed',
      },
    )
  }

  return payload as UploadReplayResult
}
