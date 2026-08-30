// T084 (US4, FR-029..FR-033): where `UploadControl` renders. `packages/design-system/specs/
// manual-upload.md` §2's own recommended gate: the three terminal-failure statuses
// `capture-state-badge.md` §3 groups as "Lost" — `unavailable`, `expired`, `failed` — and not
// `pending`/`downloading` (capture may still succeed on its own; offering an upload there invites
// a needless one that races the automatic capture) nor `quarantined` (bytes are already stored;
// an upload would be the overwrite FR-032 forbids) nor `stored` (`DownloadAction` renders in this
// exact slot instead — match-history.md §2: "mutually exclusive with `DownloadAction`").

const LOST_CAPTURE_STATUSES = new Set(['unavailable', 'expired', 'failed'])

/** `matches.py`'s raw `capture_status` (`ApiMatchDetail.capture_status`, `matches/api.ts`) — `null`
 * (no `replay_captures` row yet) is never eligible, matching `pending`/`downloading`'s own
 * "capture may still succeed" reasoning: there is nothing to rescue yet. */
export function isUploadEligible(captureStatus: string | null | undefined): boolean {
  return captureStatus != null && LOST_CAPTURE_STATUSES.has(captureStatus)
}
