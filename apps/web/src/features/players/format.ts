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
