import type { PlayerSearchResultData } from 'design-system'
import type { ApiPlayerSearchResult } from './api'

// The one place `ApiPlayerSearchResult` (snake_case, `api.ts`) becomes what `PlayerResultRow`
// (packages/design-system) expects (camelCase, `profileId` as a string, an `href` this mapper
// builds) — mirrors `features/matches/mappers.ts`'s own rule: nothing downstream of this file
// touches the raw API shape again.

export function toPlayerSearchResult(result: ApiPlayerSearchResult): PlayerSearchResultData {
  return {
    profileId: String(result.profile_id),
    // `players.$profileId.tsx` (T322) — `PlayerResultRow` never invents this path
    // (`PlayerSearchResultData.href`'s own docstring), mirroring `MatchRowData.href`'s identical
    // rule in `features/matches/mappers.ts`.
    href: `/players/${result.profile_id}`,
    alias: result.alias,
    clan: result.clan,
    country: result.country,
    gamesPlayed: result.games_played,
    // `?? null`, not a straight pass-through: `unverified_steam_id` is optional on the wire until
    // T398 lands (`ApiPlayerSearchResult`'s own docstring), and `undefined` must read the same as
    // `null` here — "not known here" — so `PlayerResultRow` never has to tell the two apart
    // (`PlayerSearchResultData.unverifiedSteamId`'s own docstring, §4a).
    unverifiedSteamId: result.unverified_steam_id ?? null,
  }
}

export function toPlayerSearchResults(
  results: readonly ApiPlayerSearchResult[],
): PlayerSearchResultData[] {
  return results.map(toPlayerSearchResult)
}
