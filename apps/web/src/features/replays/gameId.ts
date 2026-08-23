// `matches.$gameId.tsx`'s own route param is always a string — a URL segment — never the number
// `GET /api/matches/{game_id}` (`features/matches/api.ts`) and `GET
// /api/replays/{game_id}/download` both expect.

/**
 * Turns a route `gameId` param into the number the API expects, or `null` for anything that could
 * not possibly be one (non-numeric, non-integer, non-positive). `null` short-circuits straight to
 * `MatchDetailPanel`'s `not-found` state without a wasted request: FR-045 already requires an
 * unknown *numeric* id to answer the API's own `not_found`, and a `gameId` that is not even a
 * number is exactly as unknown, just detectable one step earlier — and, per FR-045, must reach
 * the identical outcome, never a different one for being caught locally rather than by the API.
 */
export function parseGameId(raw: string): number | null {
  if (!/^\d+$/.test(raw)) {
    return null
  }
  const parsed = Number(raw)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}
