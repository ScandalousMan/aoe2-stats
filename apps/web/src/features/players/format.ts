// Pure formatting — no I/O, no component knowledge. Mirrors `features/profile/format.ts`'s own
// rule; `formatRating`, `formatRank`, `formatWinRate` and `formatStreak` are reused from there
// rather than duplicated (`mappers.ts` imports them directly) — this file adds only what a third
// party's profile needs and 001's own does not: `AliasFreshnessNote`'s date.

const aliasObservedAtFormat = new Intl.DateTimeFormat('en', { dateStyle: 'medium' })

/** `ProfileSummary`'s `aliasObservedAtLabel` (003 spec §11.1.4, `AliasFreshnessNote`) — a third
 * party's alias can go stale between when this service last observed it and today; the
 * signed-in user's own never can, which is why this formatter has no equivalent in
 * `features/profile/format.ts`. */
export function formatAliasObservedAt(iso: string): string {
  return aliasObservedAtFormat.format(new Date(iso))
}

// `country-flag.md` §2a: the platform's own table, locale fixed to `en` — never the viewer's.
// Constitution XI is English-only, and a locale-dependent label would also make every visual
// baseline machine-dependent, since the name under the flag would differ between a reviewer's
// laptop and CI. Module-level: one instance, reused across every call, the same discipline
// `aliasObservedAtFormat` above already follows for `Intl.DateTimeFormat`.
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
