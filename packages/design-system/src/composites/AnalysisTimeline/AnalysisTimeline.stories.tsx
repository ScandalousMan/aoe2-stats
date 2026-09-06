import type { Meta, StoryObj } from '@storybook/react-vite'
import type { AnalysisTeamGroupData } from './index'
import { AnalysisTimeline } from './index'

const meta: Meta<typeof AnalysisTimeline> = {
  id: 'composite-analysistimeline',
  title: 'Composites/Match & game data/AnalysisTimeline',
  component: AnalysisTimeline,
}

export default meta
type Story = StoryObj<typeof AnalysisTimeline>

// Matches analysis-timeline.md §3.1's own worked example: a `Research` command for Feudal Age
// (technology id 101) at 6:41 — "ordered", never "reached".
const teams: AnalysisTeamGroupData[] = [
  {
    id: 'team-1',
    participants: [
      {
        id: 'p1',
        alias: 'GL.TheViper',
        civId: 5,
        civName: 'Britons',
        apm: 142.7,
        actions: 3821,
        villagersOrdered: 68,
        ageUps: [
          { id: 'a1', technologyId: 101, ageName: 'Feudal Age', timeMs: 401_000 },
          { id: 'a2', technologyId: 102, ageName: 'Castle Age', timeMs: 720_000 },
        ],
        builds: [
          { id: 'b1', buildingId: 70, buildingName: 'House', timeMs: 15_000 },
          { id: 'b2', buildingId: 12, buildingName: 'Barracks', timeMs: 95_000 },
        ],
        trainings: [{ id: 't1', unitId: 83, unitName: 'Villager', amount: 3, timeMs: 42_000 }],
        researches: [{ id: 'r1', technologyId: 22, technologyName: 'Loom', timeMs: 20_000 }],
        resignedAtMs: null,
      },
      {
        id: 'p2',
        alias: 'Hera',
        civId: 9,
        civName: 'Mayans',
        apm: 118.3,
        actions: 3010,
        villagersOrdered: 61,
        ageUps: [{ id: 'a3', technologyId: 101, ageName: 'Feudal Age', timeMs: 410_000 }],
        builds: [{ id: 'b3', buildingId: 70, buildingName: 'House', timeMs: 16_000 }],
        trainings: [{ id: 't2', unitId: 83, unitName: 'Villager', amount: 2, timeMs: 45_000 }],
        researches: [],
        resignedAtMs: 1_680_000,
      },
    ],
  },
]

// §3.2 — a technology, unit and building id this reference data cannot name, alongside a resolved
// name in the same frame, so the two are visibly distinct.
const teamsWithUnresolvedIdentifiers: AnalysisTeamGroupData[] = [
  {
    id: 'team-1',
    participants: [
      {
        id: 'p1',
        alias: 'DauT',
        civId: 5,
        civName: 'Britons',
        apm: 130.0,
        actions: 3500,
        villagersOrdered: 64,
        ageUps: [
          { id: 'a1', technologyId: 101, ageName: null, timeMs: 401_000 },
          { id: 'a2', technologyId: 102, ageName: 'Castle Age', timeMs: 700_000 },
        ],
        builds: [{ id: 'b1', buildingId: 9999, buildingName: null, timeMs: 15_000 }],
        trainings: [{ id: 't1', unitId: 9998, unitName: null, amount: 1, timeMs: 42_000 }],
        researches: [{ id: 'r1', technologyId: 9997, technologyName: null, timeMs: 20_000 }],
        resignedAtMs: null,
      },
    ],
  },
]

const engineProps = {
  engineName: 'aoe2rec-py',
  engineVersion: '0.1.21',
  analysedAtLabel: '23 Aug 2026',
}

export const Published: Story = {
  name: 'Published, not stale',
  args: { state: 'published', teams, ...engineProps },
}

export const PublishedAndStale: Story = {
  name: 'Published, stale — facts unchanged, Recompute offered beside them (FR-041)',
  args: { state: 'published', stale: true, teams, ...engineProps },
}

export const UnresolvedIdentifiers: Story = {
  name: 'Published — unresolved technology, unit and building ids (§3.2)',
  args: { state: 'published', teams: teamsWithUnresolvedIdentifiers, ...engineProps },
}

export const Queued: Story = {
  args: { state: 'queued' },
}

export const Running: Story = {
  args: { state: 'running' },
}

export const Failed: Story = {
  name: 'Failed — a parse is deterministic, no retry offered (§3.5)',
  args: { state: 'failed', errorClass: 'MalformedArchiveError' },
}

export const Unavailable: Story = {
  name: 'Unavailable — the recording is gone, permanently (FR-034)',
  args: { state: 'unavailable' },
}

export const Refused: Story = {
  name: 'Refused — the analysis cap is full, but it can lift (§3.5)',
  args: { state: 'refused' },
}

export const Loading: Story = {
  args: { loading: true },
}

export const LoadFailed: Story = {
  name: 'Error — the match-detail response itself failed to load (§5)',
  args: { error: true },
}

// analysis-timeline.md §5 "hover / focus-visible / active — none on `Heading`, `EngineProvenance`,
// or any list row; all are static text. `Button`s ... follow `Button`'s own states."
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The heading, the engine provenance line and every list row are static text — no hover, focus
        or active rendering of their own. The `Recompute` and "Try requesting analysis" buttons
        follow `Button`'s own states.
      </p>
      <AnalysisTimeline {...args} />
    </div>
  ),
  args: { state: 'published', teams, ...engineProps },
}

// §5 "disabled — neither `Button` has a disabled form. `Recompute` is offered only while
// `stale: true` (never rendered and disabled otherwise)... 'Try requesting analysis' is never
// disabled while shown."
export const DisabledNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      Neither button here has a disabled form — `Recompute` is offered only while the result is
      stale (absent otherwise, never disabled), and "Try requesting analysis" is never disabled
      while shown.
    </p>
  ),
}

// §5 "empty — not applicable in the sense this vocabulary usually means it: there is no
// participant list that can be legitimately empty once `state` is `published`."
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      There is no participant list that can be legitimately empty once a match is published — a real
      match's timeline is never empty, so this component has no empty rendering to show.
    </p>
  ),
}
