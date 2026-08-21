/**
 * `GET /api/profiles` names each rating entry's leaderboard itself now (`leaderboard_name`,
 * `routers/profiles.py`, T033a) — this file used to hand-maintain its own id-to-name copy, which
 * was exactly the duplicated "measured fact about an external service in a component module" the
 * three-homes rule in `CLAUDE.md` exists to prevent. What is left here is a UI display-order
 * judgement, not a fact about Relic at all, so it stays.
 */

// The order players scan a multi-board summary in, matching how the ladders are grouped in-game
// (1v1 before team, the base ruleset before its variants). Anything not in this list falls in
// afterwards, ascending by id, so the board's row order stays stable across reloads rather than
// depending on whatever order `rating_snapshots` happens to return.
const DISPLAY_ORDER = [3, 4, 13, 14, 1, 2]

export function leaderboardSortKey(leaderboardId: number): number {
  const index = DISPLAY_ORDER.indexOf(leaderboardId)
  return index === -1 ? 1000 + leaderboardId : index
}
