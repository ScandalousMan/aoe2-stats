import type {
  AgeUpEventData,
  AnalysisParticipantData,
  AnalysisTeamGroupData,
  BuildEventData,
  ResearchEventData,
  TrainingEventData,
} from 'design-system'
import type { ApiMatchParticipant } from '../matches/api'
import type {
  ApiAnalysisBuildEvent,
  ApiAnalysisDocument,
  ApiAnalysisDocumentParticipant,
  ApiAnalysisResearchEvent,
  ApiAnalysisTrainingEvent,
} from './api'

// `ApiAnalysisDocument` (`api.ts`) to `AnalysisTimeline`'s own props (packages/design-system) —
// the same "one place the wire shape becomes what the component expects" rule
// `features/matches/mappers.ts` documents for `ApiMatchDetail`.

/**
 * FR-043a: nothing in this repository names a technology, unit or building id yet — no lookup
 * exists on either side of the wire (`civilizations.py`'s own table has no counterpart for any of
 * these three kinds). Every one of them, including the three age-up technology ids
 * (`analysis-timeline.md` §3.1's own "if the lookup ever returns nothing... `UnresolvedIdentifier`
 * treatment applies"), therefore renders unresolved until such a table ships — this function
 * invents no name client-side to fill the gap.
 */
const UNRESOLVED_NAME = null

function toAgeUps(ageUpCommands: Record<string, number>): AgeUpEventData[] {
  // §3.1: "Rows are ordered chronologically, oldest first" — sorted explicitly by `timeMs` rather
  // than relying on the host engine's own object-key iteration order for integer-like keys.
  return Object.entries(ageUpCommands)
    .map(([technologyId, timeMs]) => ({
      id: `age-${technologyId}`,
      technologyId: Number(technologyId),
      ageName: UNRESOLVED_NAME,
      timeMs,
    }))
    .sort((a, b) => a.timeMs - b.timeMs)
}

function toBuilds(builds: readonly ApiAnalysisBuildEvent[]): BuildEventData[] {
  return builds.map((event, index) => ({
    id: `build-${index}`,
    buildingId: event.building_id,
    buildingName: UNRESOLVED_NAME,
    timeMs: event.world_time_ms,
  }))
}

function toTrainings(trainings: readonly ApiAnalysisTrainingEvent[]): TrainingEventData[] {
  return trainings.map((event, index) => ({
    id: `training-${index}`,
    unitId: event.unit_id,
    unitName: UNRESOLVED_NAME,
    amount: event.amount,
    timeMs: event.world_time_ms,
  }))
}

function toResearches(researches: readonly ApiAnalysisResearchEvent[]): ResearchEventData[] {
  return researches.map((event, index) => ({
    id: `research-${index}`,
    technologyId: event.technology_id,
    technologyName: UNRESOLVED_NAME,
    timeMs: event.world_time_ms,
  }))
}

/**
 * One `ApiAnalysisDocumentParticipant` (`api.ts`) as `AnalysisTimeline`'s `AnalysisParticipantData`
 * — `alias` and `civName` are not on this artifact at all (`contracts/analysis.md`'s own "carries
 * no name of any kind"); both are joined in from the match-detail participant of the same
 * `profile_id`, `matchParticipant`, exactly as `features/replays/availability.ts` joins its own
 * rows against the same list. `matchParticipant` is `undefined` only for a participant this
 * match's own roster does not carry — should not happen for a real match, but never trusted
 * blindly either (T037a), so it falls back the same way every other mapper in this app does.
 */
export function toAnalysisParticipantData(
  participant: ApiAnalysisDocumentParticipant,
  matchParticipant: ApiMatchParticipant | undefined,
): AnalysisParticipantData {
  return {
    id: String(participant.profile_id),
    alias: matchParticipant?.alias ?? 'Unknown player',
    civId: participant.civ_id,
    civName: matchParticipant?.civ_name ?? null,
    apm: participant.actions_per_minute,
    actions: participant.actions,
    villagersOrdered: participant.villagers_ordered,
    ageUps: toAgeUps(participant.age_up_commands),
    builds: toBuilds(participant.builds),
    trainings: toTrainings(participant.trainings),
    researches: toResearches(participant.researches),
    resignedAtMs: participant.resigned_at_ms,
  }
}

/**
 * Groups `document.participants` by `resolved_team_id`, in the order each team is first seen —
 * mirrors `features/matches/mappers.ts`'s `toTeamGroups`, adapted to the analysis document's own
 * field (`resolved_team_id`, always present here — `contracts/analysis.md`: "From `zheader.
 * game_settings.players`" — unlike `ApiMatchParticipant.team_id`, which can be `null`). Reusing
 * that exact ordering rule is what `analysis-timeline.md`'s own dependency note asks for: "so this
 * component reads as one more section of the same match page rather than a second,
 * differently-ordered roster."
 */
export function toAnalysisTeamGroups(
  document: ApiAnalysisDocument,
  matchParticipants: readonly ApiMatchParticipant[],
): AnalysisTeamGroupData[] {
  const byProfileId = new Map(
    matchParticipants.map((participant) => [participant.profile_id, participant] as const),
  )
  const order: number[] = []
  const byTeam = new Map<number, ApiAnalysisDocumentParticipant[]>()
  for (const participant of document.participants) {
    const teamId = participant.resolved_team_id
    if (!byTeam.has(teamId)) {
      order.push(teamId)
      byTeam.set(teamId, [])
    }
    byTeam.get(teamId)?.push(participant)
  }

  return order.map((teamId) => ({
    id: `team-${teamId}`,
    participants: (byTeam.get(teamId) ?? []).map((participant) =>
      toAnalysisParticipantData(participant, byProfileId.get(participant.profile_id)),
    ),
  }))
}
