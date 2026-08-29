import type { ReplayAvailabilityRowData, ReplayDownloadState } from 'design-system'
import type { ApiMatchParticipant } from '../matches/api'
import { toTeamGroups } from '../matches/mappers'
import type { ReplayDownloadFailure } from './downloadFailure'

// `packages/design-system/specs/replay-availability.md` §2: "same participant order as
// ParticipantsTable... grouped by team, so a reader can correlate a name to its download status
// without re-scanning against the table above it." `toTeamGroups` (`matches/mappers.ts`) already
// derives that exact order for `ParticipantsTable` itself — this reuses its ordering rather than
// re-deriving the team-grouping rule a second time and risking the two drifting apart.

//: §5's own code-to-rendering split (`downloadFailure.ts`'s module docstring): the boundary race
//: is rendered as an in-place availability transition, never a `Callout`; `rate_limited` and every
//: other failure code fall back to `ReplayAvailabilityList`'s two `Callout` states instead.
const BOUNDARY_RACE_CODE = 'expired_since_page_load'
const RATE_LIMITED_CODE = 'rate_limited'

/**
 * `ApiMatchParticipant[]` (`matches/api.ts`, carrying T338's per-participant `replay` object) to
 * `ReplayAvailabilityList`'s `ReplayAvailabilityRowData[]`. `downloadStates` is this row's own
 * in-flight download state, keyed by the same `String(profile_id)` id `onDownload` is called with
 * — absent entries default to `'idle'`, `ReplayAvailabilityList`'s own default (`index.tsx`:
 * "`idle` covers both 'never tried' and 'tried, then returned to default'").
 *
 * `failure` is the one-page-load-only result the server's `303` redirect carried
 * (`downloadFailure.ts`, `MatchDetailContainer.tsx`'s own effect) — present for at most one row,
 * the one `failure.profileId` names, and rendered instead of `downloadStates`' own entry for that
 * row alone:
 * - `expired_since_page_load` overrides that row's `availability` to `'expired'` and sets
 *   `expiredSincePageLoad`, so `ReplayAvailabilityList` renders §5's own boundary-race sentence —
 *   "This recording expired while you were viewing this page" — even though the freshly-fetched
 *   `participant.replay.availability` for that same row already reads `never_recorded` by the time
 *   this page reloads (`derive_availability`'s own `recorded_404` reading, `apps/api/.../
 *   availability.py`): the row was `obtainable` a moment ago, and that is the fact this one
 *   render states, once.
 * - `rate_limited` renders the row's own `Callout` in its rate-limit wording, carrying the exact
 *   `retryAfterSeconds` the server sent (never rounded or invented).
 * - every other code (`never_recorded`, `expired`, `not_found`) renders the generic
 *   "could not start that download" `Callout` — the request never reached a state worth a more
 *   specific message of its own.
 */
export function toReplayAvailabilityRows(
  participants: readonly ApiMatchParticipant[],
  downloadStates: Readonly<Record<string, ReplayDownloadState>> = {},
  failure?: ReplayDownloadFailure | null,
): ReplayAvailabilityRowData[] {
  const orderedIds = toTeamGroups(participants).flatMap((team) =>
    team.participants.map((participant) => participant.id),
  )
  const byId = new Map(
    participants.map((participant) => [String(participant.profile_id), participant] as const),
  )

  return orderedIds.flatMap((id) => {
    const participant = byId.get(id)
    if (!participant) {
      return []
    }
    const rowFailure = failure && failure.profileId === id ? failure : undefined
    const isBoundaryRace = rowFailure?.code === BOUNDARY_RACE_CODE
    const isRateLimited = rowFailure?.code === RATE_LIMITED_CODE

    return [
      {
        id,
        alias: participant.alias ?? 'Unknown player',
        availability: isBoundaryRace ? 'expired' : participant.replay.availability,
        obtainableUntil: participant.replay.obtainable_until,
        expiredSincePageLoad: isBoundaryRace ? true : undefined,
        downloadState: isRateLimited
          ? 'rate_limited'
          : rowFailure && !isBoundaryRace
            ? 'error'
            : (downloadStates[id] ?? 'idle'),
        retryAfterSeconds: isRateLimited ? rowFailure.retryAfterSeconds : undefined,
      },
    ]
  })
}
