import type { LinkedProfileOption, RatingEntryData, ViewedProfile } from 'design-system'
import type { ApiProfile } from './api'
import { formatRank, formatRating, formatStreak, formatWinRate } from './format'
import { leaderboardSortKey } from './leaderboards'

// The one place `ApiProfile` (snake_case, `api.ts`) becomes what `ProfileSummary`
// (packages/design-system) expects (camelCase, ids as strings). Nothing downstream of this file
// touches the raw API shape again.

export function toLinkedProfileOptions(profiles: readonly ApiProfile[]): LinkedProfileOption[] {
  return profiles.map((profile) => ({
    id: String(profile.profile_id),
    alias: profile.alias,
    isPrimary: profile.is_primary,
  }))
}

export function toViewedProfile(profile: ApiProfile): ViewedProfile {
  return {
    id: String(profile.profile_id),
    alias: profile.alias,
    country: profile.country ?? undefined,
    profileId: String(profile.profile_id),
    isPrimary: profile.is_primary,
  }
}

/** Leaderboards the profile has never played are absent from `ApiProfile.ratings` already
 * (`profiles.py`'s `_latest_ratings_by_profile` groups by `(profile_id, leaderboard_id)` over
 * `rating_snapshots`, which only ever has a row for a leaderboard actually played) — this maps
 * one-to-one rather than filtering, per FR-008 and profile-summary.md's "absent, not
 * present-and-empty". */
export function toRatingEntries(profile: ApiProfile): RatingEntryData[] {
  return [...profile.ratings]
    .sort((a, b) => leaderboardSortKey(a.leaderboard_id) - leaderboardSortKey(b.leaderboard_id))
    .map((snapshot) => ({
      leaderboardId: String(snapshot.leaderboard_id),
      leaderboardName: snapshot.leaderboard_name,
      rating: formatRating(snapshot.rating),
      // No delta: `GET /api/profiles` reports only the latest `rating_snapshots` row per
      // leaderboard (its own docstring, "most recent"), never the one before it, so there is
      // nothing to diff against here. `RatingEntryData.ratingDelta` is optional exactly for a
      // profile's first-ever snapshot; this endpoint puts every profile in that case today.
      // Computing a real delta means reading `GET /api/profiles/{id}/ratings` (contracts/http-api.md)
      // per leaderboard, out of scope for this route.
      rank: formatRank(snapshot.rank),
      wins: snapshot.wins,
      losses: snapshot.losses,
      winRate: formatWinRate(snapshot.wins, snapshot.losses),
      streak: formatStreak(snapshot.streak),
      highestRating:
        snapshot.highest_rating != null ? formatRating(snapshot.highest_rating) : undefined,
    }))
}

/** The most recent `captured_at` across every rating entry a profile carries — what
 * `formatFreshness` (`format.ts`) turns into the `FreshnessLine`. `undefined` when the profile
 * has no rating yet, which is the "empty" state's own business, not the freshness line's. */
export function latestCapturedAt(profile: ApiProfile): number | undefined {
  return profile.ratings.reduce<number | undefined>((latest, snapshot) => {
    const capturedAt = new Date(snapshot.captured_at).getTime()
    if (Number.isNaN(capturedAt)) return latest
    return latest === undefined ? capturedAt : Math.max(latest, capturedAt)
  }, undefined)
}
