import type { MatchRowData, MatchRowOpponent } from 'design-system'
import type { ApiMatchListRow, ApiOpponent } from './api'
import {
  formatCivilisation,
  formatDuration,
  formatOutcome,
  formatPlayedAtAbsolute,
  formatPlayedAtRelative,
} from './format'

// The one place `ApiMatchListRow` (snake_case, `api.ts`) becomes what `MatchRow`/`MatchList`
// (packages/design-system) expect (camelCase, ids as strings, pre-formatted text) — mirrors
// `features/profile/mappers.ts`'s own rule: nothing downstream of this file touches the raw API
// shape again.

/** match-history.md §4: "the first opposing-team participant's alias" plus `"and N others"` for
 * the remainder. **Known gap**: `ApiOpponent` carries no `team_id` (`matches.py`'s repository
 * returns every other participant regardless of team, its own `_opponents_by_game` docstring) —
 * so for a 1v1 this is exact, but for a team match the "others" count includes the caller's own
 * teammates, not only the opposing team, until the API grows a `team_id` per opponent. Reported
 * rather than silently worked around. */
export function toMatchRowOpponent(opponents: readonly ApiOpponent[]): MatchRowOpponent {
  const [first, ...rest] = opponents
  if (!first) {
    return { alias: 'Unknown opponent' }
  }
  return {
    alias: first.alias ?? 'Unknown opponent',
    othersCount: rest.length > 0 ? rest.length : undefined,
  }
}

export function toMatchRowData(row: ApiMatchListRow): MatchRowData {
  const playedAt = row.completed_at
  return {
    gameId: String(row.game_id),
    // T076's `matches.$gameId.tsx` — `MatchRow` never invents this path (match-history.md §2).
    href: `/matches/${row.game_id}`,
    outcome: formatOutcome(row.result),
    opponent: toMatchRowOpponent(row.opponents),
    map: row.map_name ?? 'Unknown map',
    civilisation: formatCivilisation(row.civilisation_name),
    ratingChange:
      row.rating_diff != null
        ? { value: row.rating_diff, formatted: String(Math.abs(row.rating_diff)) }
        : undefined,
    durationLabel: formatDuration(row.duration_seconds),
    playedAtRelative: formatPlayedAtRelative(playedAt),
    playedAtAbsolute: formatPlayedAtAbsolute(playedAt),
    captureStatus: row.capture_status,
    captureDeadlineAt: row.capture_deadline_at,
  }
}

export function toMatchRowDataList(rows: readonly ApiMatchListRow[]): MatchRowData[] {
  return rows.map(toMatchRowData)
}
