// T084 (US4, FR-029..FR-033): where `UploadControl` renders, by capture status.
// `packages/design-system/specs/manual-upload.md` §2: the three terminal-failure statuses
// `capture-state-badge.md` §3 groups as "Lost" — `unavailable`, `expired`, `failed` — and not
// `pending`/`downloading` (capture may still succeed on its own; an upload would race it) nor
// `quarantined` (bytes are already stored) nor `stored` (`DownloadAction` renders in this slot
// instead — match-history.md §2: "mutually exclusive with `DownloadAction`") nor `withdrawn` (the
// row may hold an object and the match response does not say; T727). The route refuses on its own
// and the two do not agree row for row. An objecting caller is offered it for no status
// (T723); that term is the container's, because it reads `GET /api/me`.

const LOST_CAPTURE_STATUSES = new Set(['unavailable', 'expired', 'failed'])

/** `matches.py`'s raw `capture_status` (`ApiMatchDetail.capture_status`, `matches/api.ts`) — `null`
 * (no `replay_captures` row yet) is never eligible, matching `pending`/`downloading`'s own
 * "capture may still succeed" reasoning: there is nothing to rescue yet. */
export function isUploadEligible(captureStatus: string | null | undefined): boolean {
  return captureStatus != null && LOST_CAPTURE_STATUSES.has(captureStatus)
}
