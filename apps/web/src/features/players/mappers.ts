import type { RatingEntryData, ViewedProfile } from 'design-system'
import { formatRank, formatRating, formatStreak, formatWinRate } from '../profile/format'
import { leaderboardSortKey } from '../profile/leaderboards'
import type { ApiPlayerProfile, ApiPlayerRatingSnapshot } from './api'

// The one place `ApiPlayerProfile` (snake_case, `api.ts`) becomes what `ProfileSummary`
// (packages/design-system) expects (camelCase, ids as strings) for a *third party's* profile —
// mirrors `features/profile/mappers.ts`'s own rule for the caller's own, and deliberately reuses
// its formatters (`formatRating`, `formatRank`, `formatWinRate`, `formatStreak`) and its display
// order (`leaderboardSortKey`) rather than a second copy: the two profiles are the same shapes,
// FR-008 says so, and `ProfileSummary` is the one component that renders both.

export function toViewedProfile(profile: ApiPlayerProfile): ViewedProfile {
  return {
    id: String(profile.profile_id),
    alias: profile.alias,
    country: profile.country ?? undefined,
    profileId: String(profile.profile_id),
    // A third party's profile is never the caller's own, and `ProfileSummary` never reads
    // `isPrimary` for `subject="other"` in the first place (its own module docstring).
    isPrimary: false,
  }
}

/** Leaderboards the profile has never played are absent from `ApiPlayerProfile.ratings` already
 * (`routers/players.py`'s `_profile_ratings`, same discipline as `profiles.py`) — this maps
 * one-to-one rather than filtering, per FR-008 and profile-summary.md's "absent, not
 * present-and-empty". */
export function toRatingEntries(profile: ApiPlayerProfile): RatingEntryData[] {
  return [...profile.ratings]
    .sort((a, b) => leaderboardSortKey(a.leaderboard_id) - leaderboardSortKey(b.leaderboard_id))
    .map(toRatingEntry)
}

function toRatingEntry(snapshot: ApiPlayerRatingSnapshot): RatingEntryData {
  return {
    leaderboardId: String(snapshot.leaderboard_id),
    leaderboardName: snapshot.leaderboard_name,
    rating: formatRating(snapshot.rating),
    // No delta: `GET /api/players/{profile_id}` reports only the latest snapshot per leaderboard,
    // the same rule `features/profile/mappers.ts`'s `toRatingEntries` already documents for the
    // caller's own — there is nothing to diff against here.
    rank: formatRank(snapshot.rank),
    wins: snapshot.wins,
    losses: snapshot.losses,
    winRate: formatWinRate(snapshot.wins, snapshot.losses),
    streak: formatStreak(snapshot.streak),
    highestRating:
      snapshot.highest_rating != null ? formatRating(snapshot.highest_rating) : undefined,
  }
}
