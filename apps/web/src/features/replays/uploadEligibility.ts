// T084 (US4, FR-029..FR-033): where `UploadControl` renders, by capture status.
// `packages/design-system/specs/manual-upload.md` §2: the three terminal-failure statuses
// `capture-state-badge.md` §3 groups as "Lost" — `unavailable`, `expired`, `failed` — and
// `withdrawn` when the match's `capture_object_held` is `false`, the row naming no object (T727).
// Not `pending`/`downloading` (capture may still succeed on its own; an upload would race it) nor
// `quarantined` (it may hold an object) nor `stored` (`DownloadAction` renders in this slot
// instead — match-history.md §2: "mutually exclusive with `DownloadAction`"). A `withdrawn` row
// whose `capture_object_held` is `true`, `null` or absent is withheld: only `false` says the row
// holds nothing. The route refuses on its own (manual-upload.md §4.4). An objecting caller is
// offered it for no status (T723); that term is the container's, because it reads `GET /api/me`.

const LOST_CAPTURE_STATUSES = new Set(['unavailable', 'expired', 'failed'])

/** `matches.py`'s raw `capture_status` and `capture_object_held` (`ApiMatchDetail`,
 * `matches/api.ts`). A `null` status (no `replay_captures` row yet) is never eligible, matching
 * `pending`/`downloading`'s own "capture may still succeed" reasoning: there is nothing to rescue
 * yet. `captureObjectHeld` is read for `withdrawn` alone; for the "Lost" statuses it is not
 * consulted. */
export function isUploadEligible(
  captureStatus: string | null | undefined,
  captureObjectHeld: boolean | null | undefined,
): boolean {
  if (captureStatus == null) return false
  if (captureStatus === 'withdrawn') return captureObjectHeld === false
  return LOST_CAPTURE_STATUSES.has(captureStatus)
}
