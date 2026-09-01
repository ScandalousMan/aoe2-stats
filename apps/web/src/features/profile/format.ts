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

const objectedAtFormat = new Intl.DateTimeFormat('en', { dateStyle: 'long' })

/** `ArchivalControl`'s `objectedAt` (archival-control.md §4.3), built from `archival_objected_at`
 * — `POST /api/privacy/archival-objection`'s own response right after a write, or `GET /api/me`'s
 * `AuthenticatedSession.archival_objected_at` (T406) on every later load, since both use the same
 * field name for the same timestamp (contracts/http-api.md). Renders as "on <date>", matching the
 * copy `ArchivalControl` composes it into: "Archival is off. You objected {objectedAt}." */
export function formatObjectedAt(iso: string): string {
  return `on ${objectedAtFormat.format(new Date(iso))}`
}

// `country-flag.md` §2a: the platform's own table, locale fixed to `en` — never the viewer's.
// Constitution XI is English-only, and a locale-dependent label would also make every visual
// baseline machine-dependent, since the name under the flag would differ between a reviewer's
// laptop and CI. Module-level: one instance, reused across every call, the same discipline every
// other `Intl.*Format` above already follows.
//
// Duplicated from `features/players/format.ts`'s identical `formatCountryName` rather than
// imported from there: the two features map a different `Api*Profile` to the same `ViewedProfile`
// (`mappers.ts` here, `../players/mappers.ts` there) and neither imports the other's formatters —
// this file already reuses nothing from `features/players/`, and `features/players/format.ts`
// reuses `formatRating`/`formatRank`/`formatWinRate`/`formatStreak` from here, never the reverse.
const englishRegionNames = new Intl.DisplayNames(['en'], { type: 'region' })

/** ISO 3166-1 alpha-2 — exactly two ASCII letters. Checked before handing the value to
 * `Intl.DisplayNames.of`, which throws `RangeError` on some malformed subtags rather than
 * returning `undefined` for one; this also doubles as the "is this actually a code" test
 * `country-flag.md` §2a's third bullet needs. */
function isAlpha2CountryCode(value: string): boolean {
  return /^[A-Za-z]{2}$/.test(value)
}

/** `country-flag.md` §2a: turns the API's ISO alpha-2 `country` code ("fr") into an English
 * display name ("France") for `ViewedProfile.countryName`. Absent, `null` or blank after
 * trimming resolves to `undefined` — `CountryFlag`'s (packages/design-system) own "no country at
 * all" case (`country-flag.md` §4), never an empty string or a placeholder.
 *
 * **A value that is not a two-letter code is shown verbatim.** `country` is typed `str | None`
 * all the way from the provider (`packages/providers/src/aoe2stats_providers/base.py`), so a
 * source that one day sends `"Germany"` instead of `"de"` renders "Germany" rather than a mangled
 * lookup — the only thing a non-code value can be is a name already. */
export function formatCountryName(country: string | null | undefined): string | undefined {
  if (country == null) return undefined
  const trimmed = country.trim()
  if (trimmed === '') return undefined
  if (!isAlpha2CountryCode(trimmed)) return trimmed
  return englishRegionNames.of(trimmed.toUpperCase()) ?? trimmed
}
