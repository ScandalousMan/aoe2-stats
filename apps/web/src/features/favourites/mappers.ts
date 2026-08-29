import type { FavouriteEntryData, FavouriteStandingData } from 'design-system'
import { formatRank, formatRating } from '../profile/format'
import { leaderboardSortKey } from '../profile/leaderboards'
import type { ApiFavouriteEntry, ApiFavouriteRatingSnapshot } from './api'

// The one place `ApiFavouriteEntry` (snake_case, `api.ts`) becomes what `FavouriteRow`
// (packages/design-system, `favourites-list.md`) expects — mirrors `features/players/mappers.ts`'s
// and `features/search/mappers.ts`'s own rule: nothing downstream of this file touches the raw API
// shape again.

/** favourites-list.md §4: "current rating and rank on the player's primary ladder" — the same
 * 1v1-before-team display order `ProfileSummary`'s own `RatingBoard` uses
 * (`features/players/mappers.ts`'s identical `leaderboardSortKey` reuse), picking the
 * highest-priority ladder this player has actually played rather than a fixed leaderboard id. */
function primaryRating(
  ratings: readonly ApiFavouriteRatingSnapshot[],
): ApiFavouriteRatingSnapshot | undefined {
  return [...ratings].sort(
    (a, b) => leaderboardSortKey(a.leaderboard_id) - leaderboardSortKey(b.leaderboard_id),
  )[0]
}

function toStanding(ratings: readonly ApiFavouriteRatingSnapshot[]): FavouriteStandingData {
  const primary = primaryRating(ratings)
  // favourites-list.md §4, "never played a ranked ladder": `StatValue`'s own empty state — a
  // text-secondary em dash, never a fabricated `0` (US5 scenario 3 reaches a favourite of any
  // kind, spec.md's own edge case). `StatValue`'s `status="empty"` branch never reads `value`.
  if (!primary) {
    return { status: 'empty', label: 'Rating', secondaryLine: 'Not ranked yet' }
  }
  const rank = formatRank(primary.rank)
  return {
    label: primary.leaderboard_name,
    value: formatRating(primary.rating),
    // Relic's own "not enough games for a rank yet" convention (`formatRank`'s own docstring) —
    // absent, never a fabricated rank, mirroring `features/players/mappers.ts`'s identical rule.
    unit: rank ? `Rank ${rank}` : undefined,
  }
}

export interface ToFavouriteEntryOptions {
  /** `FavouriteToggle`'s own `loading`, for this entry's `DELETE` in flight (favourites-list.md
   * §5, "loading"). */
  removing?: boolean
}

export function toFavouriteEntryData(
  entry: ApiFavouriteEntry,
  { removing }: ToFavouriteEntryOptions = {},
): FavouriteEntryData {
  return {
    profileId: String(entry.profile_id),
    // `routes/players.$profileId.index.tsx` — `FavouritesList` never invents this path
    // (`FavouriteEntryData.href`'s own docstring), the same discipline
    // `features/search/mappers.ts` gives `PlayerSearchResultData.href`.
    href: `/players/${entry.profile_id}`,
    // `routers/favourites.py`'s `list_favourites`: `alias` is `null` only when the favourited
    // profile itself has vanished (`ApiFavouriteEntry.alias`'s own docstring) — a fallback string
    // keeps the row, and its remove control, reachable rather than silently dropping a bookmark
    // the caller can no longer explain.
    alias: entry.alias ?? `Player ${entry.profile_id}`,
    // Absent when unknown, never blank-filled (favourites-list.md §4, the same rule
    // `player-search.md` §4 states) — `null` already reads that way to `FavouriteEntryData`.
    country: entry.country,
    standing: toStanding(entry.ratings),
    removing,
  }
}

export function toFavouriteEntries(
  entries: readonly ApiFavouriteEntry[],
  removingProfileIds: ReadonlySet<string> = new Set(),
): FavouriteEntryData[] {
  return entries.map((entry) =>
    toFavouriteEntryData(entry, { removing: removingProfileIds.has(String(entry.profile_id)) }),
  )
}
