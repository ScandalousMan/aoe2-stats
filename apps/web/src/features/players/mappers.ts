import type { RatingEntryData, ViewedProfile } from 'design-system'
import { countryFlag } from 'game-assets'
import { formatRank, formatRating, formatStreak, formatWinRate } from '../profile/format'
import { leaderboardSortKey } from '../profile/leaderboards'
import type { ApiPlayerProfile, ApiPlayerRatingSnapshot } from './api'
import { formatCountryName } from './format'

// The one place `ApiPlayerProfile` (snake_case, `api.ts`) becomes what `ProfileSummary`
// (packages/design-system) expects (camelCase, ids as strings) for a *third party's* profile —
// mirrors `features/profile/mappers.ts`'s own rule for the caller's own, and deliberately reuses
// its formatters (`formatRating`, `formatRank`, `formatWinRate`, `formatStreak`) and its display
// order (`leaderboardSortKey`) rather than a second copy: the two profiles are the same shapes,
// FR-008 says so, and `ProfileSummary` is the one component that renders both.

/** `country-flag.md` §2a's last paragraph: the flag URL is resolved the same way and in the same
 * place as the name (`formatCountryName`, `./format.ts`), from the raw code — `undefined` on a
 * `null` country or a pack miss alike (`packages/game-assets`'s `countryFlag`), passed straight
 * through to `CountryFlag`'s own "no picture, name alone" render (`country-flag.md` §4). Same
 * `undefined`-on-null-or-miss rule `features/matches/mappers.ts`'s `resolveCivIconUrl` already
 * documents for the equivalent civilisation/map lookups (004 T432). */
function resolveCountryFlagUrl(country: string | null): string | undefined {
  return country != null ? countryFlag(country) : undefined
}

export function toViewedProfile(profile: ApiPlayerProfile): ViewedProfile {
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
