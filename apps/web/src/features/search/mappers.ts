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
  }
}

export function toPlayerSearchResults(
  results: readonly ApiPlayerSearchResult[],
): PlayerSearchResultData[] {
  return results.map(toPlayerSearchResult)
}
