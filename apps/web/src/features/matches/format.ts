// Pure formatting — no I/O, no component knowledge, mirroring `features/profile/format.ts`'s own
// rule: `MatchRow`/`MatchList` (packages/design-system) take every figure pre-formatted as text.

const relativeTimeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** `MatchRowData.playedAtRelative` — "3 hours ago", never "Updated ..." (that prefix is
 * `features/profile/format.ts`'s `formatFreshness`, a different sentence for a different field).
 * `playedAt` is always in the past here (a completed match), so this only ever reads backwards. */
export function formatPlayedAtRelative(playedAt: string, now: number = Date.now()): string {
  const diffMs = new Date(playedAt).getTime() - now
  if (Math.abs(diffMs) < MINUTE) return 'just now'
  if (Math.abs(diffMs) < HOUR)
    return relativeTimeFormat.format(Math.round(diffMs / MINUTE), 'minute')
  if (Math.abs(diffMs) < DAY) return relativeTimeFormat.format(Math.round(diffMs / HOUR), 'hour')
  return relativeTimeFormat.format(Math.round(diffMs / DAY), 'day')
}

const absoluteDateTimeFormat = new Intl.DateTimeFormat('en', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** `MatchRowData.playedAtAbsolute` — the native `title` tooltip text (match-history.md §2). */
export function formatPlayedAtAbsolute(playedAt: string): string {
  return absoluteDateTimeFormat.format(new Date(playedAt))
}

/** `MatchRowData.durationLabel` — "34 min", never raw seconds (match-history.md §2). Rounds to
 * the nearest minute; a match under 60 s (should not happen for a ranked game, but not this
 * function's business to assume) reads as "0 min" rather than "NaN min". */
export function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds == null) return 'Unknown duration'
  const minutes = Math.round(durationSeconds / 60)
  return `${minutes} min`
}

/** `MatchRowData.outcome` — the API's `result` is `"win"` or `"loss"` today (`api.ts`'s own note);
 * anything else (should not happen, but a network payload is never trusted blindly per T037a)
 * falls back to `"loss"` rather than letting an unrecognised string reach a component whose type
 * demands exactly one of the two. */
export function formatOutcome(result: string | null): 'win' | 'loss' {
  return result === 'win' ? 'win' : 'loss'
}

/** `MatchRowData.civilisation` — the API reports only the caller's numeric `civ_id`
 * (`api.ts`'s own note on `matches.py`'s `civilisation` field); there is no `civilisation_name`
 * field the way `GET /api/profiles` now sends `leaderboard_name` (T033a). Rendering the id is a
 * known, reported gap (see this feature's implementation notes) rather than a hand-maintained
 * id-to-name table repeating the exact duplication T033a moved server-side for leaderboards. */
export function formatCivilisation(civId: number | null): string {
  return civId != null ? `Civilisation ${civId}` : 'Unknown civilisation'
}
