// Pure formatting — no I/O, no component knowledge. `ProfileSummary` (packages/design-system)
// takes every figure pre-formatted as text (StatValue "does not localise numbers", per its own
// spec), so this is the one place that decides how a number becomes the string on screen.

export function formatRating(rating: number): string {
  return rating.toLocaleString('en-US')
}

/** Relic's `getPersonalStat` returns `-1` (occasionally `0`) for "not enough games for a rank
 * yet", never a real rank in that range (`api.ts`'s `ApiRatingSnapshot.rank` docstring) — `undefined`
 * here is exactly what tells `ProfileSummary` to render its provisional "Not ranked yet" state
 * instead of a false rank. */
export function formatRank(rank: number | null): string | undefined {
  if (rank == null || rank <= 0) return undefined
  return rank.toLocaleString('en-US')
}

export function formatWinRate(wins: number, losses: number): string {
  const total = wins + losses
  if (total === 0) return '0%'
  return `${Math.round((wins / total) * 100)}%`
}

/** Relic's sign convention: positive is a win streak, negative a loss streak, zero (or absent) is
 * no current streak — `ProfileSummary` only renders `Streak` when this is truthy, so a zero
 * streak correctly disappears rather than showing "W0". */
export function formatStreak(streak: number | null | undefined): string | undefined {
  if (!streak) return undefined
  return streak > 0 ? `W${streak}` : `L${Math.abs(streak)}`
}

const relativeTimeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const absoluteTimeFormat = new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit' })

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** `ProfileSummary`'s `FreshnessLine`: when the figures on screen were measured, in both relative
 * and absolute time (profile-summary.md §5, "error"). `measuredAt` is `undefined` before the
 * first successful fetch has ever landed, in which case there is nothing to report yet. */
export function formatFreshness(
  measuredAt: number | undefined,
  now: number = Date.now(),
): string | undefined {
  if (measuredAt === undefined) return undefined

  const diffMs = measuredAt - now
  let relative: string
  if (Math.abs(diffMs) < MINUTE) {
    relative = 'just now'
  } else if (Math.abs(diffMs) < HOUR) {
    relative = relativeTimeFormat.format(Math.round(diffMs / MINUTE), 'minute')
  } else if (Math.abs(diffMs) < DAY) {
    relative = relativeTimeFormat.format(Math.round(diffMs / HOUR), 'hour')
  } else {
    relative = relativeTimeFormat.format(Math.round(diffMs / DAY), 'day')
  }

  const absolute = absoluteTimeFormat.format(new Date(measuredAt))
  return relative === 'just now'
    ? `Updated just now (${absolute})`
    : `Updated ${relative} (${absolute})`
}

const recordedAtFormat = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

/** `ConsentStep`'s `recordedAt` (consent-step.md §4.4), built from `ingest_consent_at` —
 * `POST /api/privacy/consent`'s own response right after a write, or `GET /api/me`'s
 * `AuthenticatedSession.ingest_consent_at` (T037a) on every later load, since both use the same
 * field name for the same timestamp (contracts/http-api.md). */
export function formatRecordedAt(iso: string): string {
  return recordedAtFormat.format(new Date(iso))
}
