import type {
  AgeUpEventData,
  AnalysisParticipantData,
  AnalysisTeamGroupData,
  BuildEventData,
  ResearchEventData,
  TrainingEventData,
} from 'design-system'
import type { ApiMatchParticipant } from '../matches/api'
import { readKnowledgeNames } from './api'
import type {
  ApiAnalysisBuildEvent,
  ApiAnalysisDocument,
  ApiAnalysisDocumentParticipant,
  ApiAnalysisResearchEvent,
  ApiAnalysisTrainingEvent,
  ApiKnowledgeNames,
} from './api'

// `ApiAnalysisDocument` (`api.ts`) to `AnalysisTimeline`'s own props (packages/design-system) —
// the same "one place the wire shape becomes what the component expects" rule
// `features/matches/mappers.ts` documents for `ApiMatchDetail`.

/**
 * FR-043a, T709: the page never invents a name. A name is shown only when the response carries one
 * for that id (`GET /api/matches/{game_id}/analysis` serves them beside the stored document,
 * resolved from the knowledge snapshot the document's own identity names); an id the snapshot does
 * not name, a document whose identity names no snapshot, and a response with no names at all
 * render unresolved, as every id did before names were served. This function substitutes nothing
 * and tries no other kind's table for an id.
 */
const UNRESOLVED_NAME = null

function nameOf(table: Record<string, string> | undefined, id: number): string | null {
  return table?.[String(id)] ?? UNRESOLVED_NAME
}

function toAgeUps(
  ageUpCommands: Record<string, number>,
  names: ApiKnowledgeNames | null,
): AgeUpEventData[] {
  // §3.1: "Rows are ordered chronologically, oldest first" — sorted explicitly by `timeMs` rather
  // than relying on the host engine's own object-key iteration order for integer-like keys.
  return Object.entries(ageUpCommands)
    .map(([technologyId, timeMs]) => ({
      id: `age-${technologyId}`,
      technologyId: Number(technologyId),
      ageName: nameOf(names?.technology, Number(technologyId)),
      timeMs,
    }))
    .sort((a, b) => a.timeMs - b.timeMs)
}

function toBuilds(
  builds: readonly ApiAnalysisBuildEvent[],
  names: ApiKnowledgeNames | null,
): BuildEventData[] {
  return builds.map((event, index) => ({
    id: `build-${index}`,
    buildingId: event.building_id,
    buildingName: nameOf(names?.building, event.building_id),
    timeMs: event.world_time_ms,
  }))
}

function toTrainings(
  trainings: readonly ApiAnalysisTrainingEvent[],
  names: ApiKnowledgeNames | null,
): TrainingEventData[] {
  return trainings.map((event, index) => ({
    id: `training-${index}`,
    unitId: event.unit_id,
    unitName: nameOf(names?.unit, event.unit_id),
    amount: event.amount,
    timeMs: event.world_time_ms,
  }))
}

function toResearches(
  researches: readonly ApiAnalysisResearchEvent[],
  names: ApiKnowledgeNames | null,
): ResearchEventData[] {
  return researches.map((event, index) => ({
    id: `research-${index}`,
    technologyId: event.technology_id,
    technologyName: nameOf(names?.technology, event.technology_id),
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
  names: ApiKnowledgeNames | null = null,
): AnalysisParticipantData {
  return {
    id: String(participant.profile_id),
    alias: matchParticipant?.alias ?? 'Unknown player',
    civId: participant.civ_id,
    civName: matchParticipant?.civ_name ?? null,
    apm: participant.actions_per_minute,
    actions: participant.actions,
    villagersOrdered: participant.villagers_ordered,
    ageUps: toAgeUps(participant.age_up_commands, names),
    builds: toBuilds(participant.builds, names),
    trainings: toTrainings(participant.trainings, names),
    researches: toResearches(participant.researches, names),
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
  const names = readKnowledgeNames(document.knowledge_names)
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
      toAnalysisParticipantData(participant, byProfileId.get(participant.profile_id), names),
    ),
  }))
}
