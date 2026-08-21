/**
 * `GET /api/profiles` (`apps/api/.../routers/profiles.py`) carries a bare `leaderboard_id`
 * integer, never a name — Relic's `getPersonalStat` doesn't return one either
 * (`packages/providers/fixtures/relic/get_personal_stat.json`), and nothing in `data-model.md`
 * stores one. `profile-summary.md`'s anatomy still requires a `LeaderboardName` per entry
 * (FR-008), so this file is where that text comes from.
 *
 * Only the ladders this file can name with confidence are listed. This app makes no network call
 * outside `packages/providers` (constitution III) and cannot look the rest up against
 * `getAvailableLeaderboards`, so an id this map does not recognise renders as "Leaderboard <id>"
 * rather than a guessed name that might be wrong. Reported alongside this task: a proper mapping
 * belongs in the backend (`GET /api/profiles` naming its own leaderboards, or a stored reference
 * table), not duplicated by hand here.
 */
const KNOWN_LEADERBOARD_NAMES: Readonly<Record<number, string>> = {
  1: '1v1 Death Match',
  2: 'Team Death Match',
  3: '1v1 Random Map',
  4: 'Team Random Map',
  13: '1v1 Empire Wars',
  14: 'Team Empire Wars',
}

export function leaderboardName(leaderboardId: number): string {
  return KNOWN_LEADERBOARD_NAMES[leaderboardId] ?? `Leaderboard ${leaderboardId}`
}

// The order players scan a multi-board summary in, matching how the ladders are grouped in-game
// (1v1 before team, the base ruleset before its variants). Anything not in this list falls in
// afterwards, ascending by id, so the board's row order stays stable across reloads rather than
// depending on whatever order `rating_snapshots` happens to return.
const DISPLAY_ORDER = [3, 4, 13, 14, 1, 2]

export function leaderboardSortKey(leaderboardId: number): number {
  const index = DISPLAY_ORDER.indexOf(leaderboardId)
  return index === -1 ? 1000 + leaderboardId : index
}
