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
 * same-tab navigation to the download endpoint... the URL is minted per click so FR-029's
 * access-log write happens server-side on that request, on every click, archived and obtainable
 * alike"). `path` is `matches/api.ts`'s own `ApiReplayAvailability.download_path`, server-minted —
 * never rebuilt client-side, matching every other identifier this feature refuses to derive on
 * its own (module docstring above).
 *
 * The same reasoning `triggerReplayDownload` carries applies twice over here: this single route
 * answers a 302-to-a-signed-URL for `archived` (a *cross-origin* redirect — the bucket has no
 * CORS configured, `packages/storage/src/aoe2stats_storage/objects.py`'s own docstring, so a
 * script-readable `fetch` following it would reject on the browser's own CORS check) and a
 * same-origin streamed body for `obtainable` (FR-027: fetched from the source and streamed
 * straight through, never stored). A plain top-level navigation is the one mechanism that serves
 * both without a second, divergent code path per state.
 */
export function triggerReplayPointOfViewDownload(path: string): void {
  window.location.assign(path)
}
