import type { ReplayAvailabilityRowData, ReplayDownloadState } from 'design-system'
import type { ApiMatchParticipant } from '../matches/api'
import { toTeamGroups } from '../matches/mappers'

// `packages/design-system/specs/replay-availability.md` §2: "same participant order as
// ParticipantsTable... grouped by team, so a reader can correlate a name to its download status
// without re-scanning against the table above it." `toTeamGroups` (`matches/mappers.ts`) already
// derives that exact order for `ParticipantsTable` itself — this reuses its ordering rather than
// re-deriving the team-grouping rule a second time and risking the two drifting apart.

/**
 * `ApiMatchParticipant[]` (`matches/api.ts`, carrying T338's per-participant `replay` object) to
 * `ReplayAvailabilityList`'s `ReplayAvailabilityRowData[]`. `downloadStates` is this row's own
 * in-flight download state, keyed by the same `String(profile_id)` id `onDownload` is called with
 * — absent entries default to `'idle'`, `ReplayAvailabilityList`'s own default (`index.tsx`:
 * "`idle` covers both 'never tried' and 'tried, then returned to default'").
 */
export function toReplayAvailabilityRows(
  participants: readonly ApiMatchParticipant[],
  downloadStates: Readonly<Record<string, ReplayDownloadState>> = {},
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
    return [
      {
        id,
        alias: participant.alias ?? 'Unknown player',
        availability: participant.replay.availability,
        obtainableUntil: participant.replay.obtainable_until,
        downloadState: downloadStates[id] ?? 'idle',
      },
    ]
  })
}
