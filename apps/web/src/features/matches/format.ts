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

/** `MatchRowData.outcome` / `ParticipantData.result` — `match_players.result` is `null` for every
 * row this system has written so far (no enrichment stage yet fills it in — `discover.py`'s own
 * `upsert_match_player` docstring), and a wire payload is never trusted blindly either (T037a), so
 * anything that is not literally `"win"` or `"loss"` reads as **`"unknown"`**, never as a guessed
 * `"loss"`. Coercing an unknown result to a loss used to render a match this service has no result
 * for as a confident, false defeat for every participant — the same failure FR-020 already forbids
 * for a name this service cannot resolve (match-history.md §2a), applied here to `result` instead.
 * `MatchRow`/`MatchDetailPanel` (packages/design-system) render `"unknown"` as its own state, never
 * folded into `"loss"`. */
export function formatOutcome(result: string | null): 'win' | 'loss' | 'unknown' {
  if (result === 'win') return 'win'
  if (result === 'loss') return 'loss'
  return 'unknown'
}

/** `MatchRowData.civilisation` — `matches.py` now sends `civilisation_name` alongside the raw
 * `civilisation` id (T070c), the same shape `GET /api/profiles`'s `leaderboard_name` already
 * established (T033a): a hand-maintained id-to-name table has no business in this module, so this
 * function no longer builds one — it passes the server's own name straight through, falling back
 * only for a match with no recorded civilisation at all (`civilisation_name` and `civilisation`
 * are both `null` together, never one without the other — `matches.py`'s own `civilisation_name`
 * docstring). */
export function formatCivilisation(civilisationName: string | null): string {
  return civilisationName ?? 'Unknown civilisation'
}
