import type {
  MatchDetailData,
  MatchParticipantResult,
  MatchRowData,
  MatchRowParticipant,
  ParticipantData,
  TeamGroupData,
} from 'design-system'
import type {
  ApiMatchDetail,
  ApiMatchListRow,
  ApiMatchParticipant,
  ApiMatchRowParticipant,
} from './api'
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

/** `ApiMatchRowParticipant.result` narrowed to `MatchParticipantResult` — mirrors
 * `formatOutcome`'s own defensiveness (T037a: a wire payload is never trusted blindly), but keeps
 * `null` as `null` rather than coercing it to `MatchRow`'s row-level `"unknown"` union: §12.3's
 * `TeamResult` marker needs the real three-value fact per participant, not the row's own read. */
function toParticipantResult(result: string | null): MatchParticipantResult {
  return result === 'win' || result === 'loss' ? result : null
}

/** One `ApiMatchRowParticipant` as `MatchRow`'s own `MatchRowParticipant` (match-history.md
 * §12.3) — `isViewer` is computed here, from the profile whose history this page is (never a
 * client-side guess), so `MatchRow` itself never needs a `perspective` prop (§11.3's rule,
 * extended to the ordering §12.3 introduces). */
export function toMatchRowParticipant(
  participant: ApiMatchRowParticipant,
  viewerProfileId: number,
): MatchRowParticipant {
  return {
    profileId: participant.profile_id,
    alias: participant.alias ?? 'Unknown player',
    teamId: participant.team_id,
    colorId: participant.color_id,
    result: toParticipantResult(participant.result),
    isViewer: participant.profile_id === viewerProfileId,
  }
}

export function toMatchRowData(row: ApiMatchListRow, viewerProfileId: number): MatchRowData {
  const playedAt = row.completed_at
  return {
    gameId: String(row.game_id),
    // T076's `matches.$gameId.tsx` — `MatchRow` never invents this path (match-history.md §2).
    href: `/matches/${row.game_id}`,
    outcome: formatOutcome(row.result),
    participants: row.participants.map((participant) =>
      toMatchRowParticipant(participant, viewerProfileId),
    ),
    map: row.map_name ?? 'Unknown map',
    civilisation: formatCivilisation(row.civilisation_name),
    leaderboardName: row.leaderboard_name,
    // Icon/thumbnail resolution through `packages/game-assets` is T432's own step, not yet wired
    // here — `civIconUrl`/`mapThumbnailUrl` stay `undefined`, `MatchRow`'s own designed degrade
    // path (match-history.md §12.1 rule 3), never a placeholder.
    rating: row.rating,
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

export function toMatchRowDataList(
  rows: readonly ApiMatchListRow[],
  viewerProfileId: number,
): MatchRowData[] {
  return rows.map((row) => toMatchRowData(row, viewerProfileId))
}

// --- GET /api/matches/{game_id} -> MatchDetailPanel (T076) --------------------------------------

/** One `ApiMatchParticipant` (`api.ts`) as `MatchDetailPanel`'s `ParticipantData`
 * (match-history.md §2's `ParticipantsTable`) — team grouping happens one level up, in
 * `toTeamGroups`, since a single participant carries only its own `team_id`, never its
 * teammates.
 *
 * `civId`/`civName` travel through separately, unlike `MatchRowData.civilisation`'s single
 * pre-formatted string: match-history.md §11.2 forbids filling an unresolved `civ_name` in with
 * the raw id (or a guessed label) as if it were a name, so `MatchDetailPanel`'s own
 * `UnresolvedIdentifier` renders `civId` only when `civName` is `null` — this mapper must not
 * pre-empt that with `formatCivilisation`'s row-level "Unknown civilisation" fallback, which is a
 * different, allowed treatment for a different field (`toMatchRowData` below). */
export function toParticipantData(participant: ApiMatchParticipant): ParticipantData {
  return {
    id: String(participant.profile_id),
    alias: participant.alias ?? 'Unknown player',
    civId: participant.civ_id,
    civName: participant.civ_name,
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
    // §11.2: unlike `MatchRowData.map`'s "Unknown map" fallback, `MatchDetailPanel`'s header
    // renders a `null` map via its own `UnresolvedIdentifier` (no id to show for a map, per that
    // component's own note) — this mapper must not paper over the gap with invented text.
    map: detail.map_name,
    // T070f: `leaderboard_name` computed server-side (`matches.py`'s `_match_detail_json`), the
    // same `leaderboards.py` mapping `GET /api/profiles` already reads — passed straight through,
    // never re-derived here.
    leaderboardName: detail.leaderboard_name,
    durationLabel: formatDuration(detail.duration_seconds),
    // "Played-on date/time" (match-history.md §2) reads most naturally as when the match started;
    // `started_at` can be `null` (module docstring on `ApiMatchDetail`), so this falls back to
    // `completed_at` — always present — rather than showing nothing.
    playedAtLabel: formatPlayedAtAbsolute(detail.started_at ?? detail.completed_at),
    // §11.1 point 3: raw text exactly as reported, never resolved to a name and never subject to
    // §11.2's unresolved treatment — `detail.patch` passed straight through, `null` and all.
    gameVersion: detail.patch,
    teams: toTeamGroups(detail.participants),
    captureStatus: detail.capture_status,
    captureDeadlineAt: detail.capture_deadline_at,
  }
}
