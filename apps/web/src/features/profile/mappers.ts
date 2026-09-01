import type { LinkedProfileOption, RatingEntryData, ViewedProfile } from 'design-system'
import { countryFlag } from 'game-assets'
import type { ApiProfile } from './api'
import { formatCountryName, formatRank, formatRating, formatStreak, formatWinRate } from './format'
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

/** `country-flag.md` §2a's last paragraph: the flag URL is resolved the same way and in the same
 * place as the name (`formatCountryName`, `./format.ts`), from the raw code — `undefined` on a
 * `null` country or a pack miss alike (`packages/game-assets`'s `countryFlag`), passed straight
 * through to `CountryFlag`'s own "no picture, name alone" render (`country-flag.md` §4). Mirrors
 * `features/players/mappers.ts`'s identical `resolveCountryFlagUrl` for the same reason `mappers.ts`
 * elsewhere in this file duplicates nothing shared — see `format.ts`'s note on `formatCountryName`. */
function resolveCountryFlagUrl(country: string | null): string | undefined {
  return country != null ? countryFlag(country) : undefined
}

export function toViewedProfile(profile: ApiProfile): ViewedProfile {
  return {
    id: String(profile.profile_id),
    alias: profile.alias,
    // 004 spec §12.4: the raw `country` code never reaches `ProfileSummary` — `countryName` (an
    // English display name, or the value verbatim when it is not a two-letter code) and
    // `countryFlagUrl` replace it, both resolved here and nowhere downstream.
    countryName: formatCountryName(profile.country),
    countryFlagUrl: resolveCountryFlagUrl(profile.country),
    // 004 spec §12.5: a hash, never a URL — passed straight through, `null` and all;
    // `PlayerAvatar` (packages/design-system) builds the CDN URL and owns the fallback.
    avatarHash: profile.avatar_hash,
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
