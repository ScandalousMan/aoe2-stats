import type {
  MatchDetailData,
  MatchRowData,
  MatchRowOpponent,
  ParticipantData,
  TeamGroupData,
} from 'design-system'
import type { ApiMatchDetail, ApiMatchListRow, ApiMatchParticipant, ApiOpponent } from './api'
import {
  formatCivilisation,
  formatDuration,
  formatLeaderboardName,
  formatOutcome,
  formatPlayedAtAbsolute,
  formatPlayedAtRelative,
} from './format'

// The one place `ApiMatchListRow` (snake_case, `api.ts`) becomes what `MatchRow`/`MatchList`
// (packages/design-system) expect (camelCase, ids as strings, pre-formatted text) — mirrors
// `features/profile/mappers.ts`'s own rule: nothing downstream of this file touches the raw API
// shape again.

/** match-history.md §4: "the first opposing-team participant's alias" plus `"and N others"` for
 * the remainder. `row.opponents` (`api.ts`) is already restricted to the opposing team(s) —
 * `matches.py`'s `_opponents_by_game` excludes the caller's own teammates at the query (T070d) —
 * so for both a 1v1 and a team match, every entry here is a genuine opponent and `rest.length`
 * is exactly the "and N others" count FR-010 asks for. */
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

// --- GET /api/matches/{game_id} -> MatchDetailPanel (T076) --------------------------------------

/** One `ApiMatchParticipant` (`api.ts`) as `MatchDetailPanel`'s `ParticipantData`
 * (match-history.md §2's `ParticipantsTable`) — team grouping happens one level up, in
 * `toTeamGroups`, since a single participant carries only its own `team_id`, never its
 * teammates. */
export function toParticipantData(participant: ApiMatchParticipant): ParticipantData {
  return {
    id: String(participant.profile_id),
    alias: participant.alias ?? 'Unknown player',
    civilisation: formatCivilisation(participant.civ_name),
    result: formatOutcome(participant.result),
    ratingChange:
      participant.rating_diff != null
        ? { value: participant.rating_diff, formatted: String(Math.abs(participant.rating_diff)) }
        : undefined,
  }
}

/** Groups every participant of one match by `team_id`, in the order each team is first seen —
 * `MatchDetailPanel`'s `TeamGroup`s (match-history.md §2). A `null` `team_id` (no team recorded
 * for that participant — should not happen for a ranked match, but a wire response is never
 * trusted blindly per T037a) is its own trailing group rather than silently dropped or merged
 * into a real team. */
export function toTeamGroups(participants: readonly ApiMatchParticipant[]): TeamGroupData[] {
  const order: (number | null)[] = []
  const byTeam = new Map<number | null, ApiMatchParticipant[]>()
  for (const participant of participants) {
    const key = participant.team_id
    if (!byTeam.has(key)) {
      order.push(key)
      byTeam.set(key, [])
    }
    byTeam.get(key)?.push(participant)
  }
  // Real teams first, in the order first seen; the no-team group (if any) always trails, so an
  // exceptional match never pushes real teams out of their natural reading order.
  const realTeams = order.filter((teamId) => teamId !== null)
  const orderedKeys = order.includes(null) ? [...realTeams, null] : realTeams

  return orderedKeys.map((teamId) => ({
    id: teamId !== null ? `team-${teamId}` : 'team-none',
    name: teamId !== null ? `Team ${teamId}` : 'No team recorded',
    participants: (byTeam.get(teamId) ?? []).map(toParticipantData),
  }))
}

/** `ApiMatchDetail` (`api.ts`) to `MatchDetailPanel`'s `MatchDetailData`. `captureStatus` and
 * `captureDeadlineAt` travel through verbatim (T070e: `_match_detail_json` now computes both, the
 * same way `_match_row_json` already did) — no collapse here either, `CaptureStateBadge` is where
 * the seven raw `CaptureStatus` values become the badge's four states (capture-state-badge.md
 * §3). This is what lets `MatchDetailPanel`'s `DownloadAction` gate (`captureStatus === 'stored'`)
 * fire for real. */
export function toMatchDetailData(detail: ApiMatchDetail): MatchDetailData {
  return {
    gameId: String(detail.game_id),
    map: detail.map_name ?? 'Unknown map',
    leaderboardName: formatLeaderboardName(detail.leaderboard_id),
    durationLabel: formatDuration(detail.duration_seconds),
    // "Played-on date/time" (match-history.md §2) reads most naturally as when the match started;
    // `started_at` can be `null` (module docstring on `ApiMatchDetail`), so this falls back to
    // `completed_at` — always present — rather than showing nothing.
    playedAtLabel: formatPlayedAtAbsolute(detail.started_at ?? detail.completed_at),
    teams: toTeamGroups(detail.participants),
    captureStatus: detail.capture_status,
    captureDeadlineAt: detail.capture_deadline_at,
  }
}
