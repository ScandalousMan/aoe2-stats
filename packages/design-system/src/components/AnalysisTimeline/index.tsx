import type { ReactNode } from 'react'
import { useId } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Badge } from '../Badge'
import { Button } from '../Button'
import type { CalloutTone } from '../Callout'
import { Callout } from '../Callout'
import { UnresolvedIdentifier } from '../MatchDetailPanel'
import { Skeleton } from '../Skeleton'
import { StatValue } from '../StatValue'

// packages/design-system/specs/analysis-timeline.md

export type AnalysisState =
  'queued' | 'running' | 'published' | 'failed' | 'unavailable' | 'refused'

export interface AgeUpEventData {
  /** React list key. */
  id: string
  /** `age_up_commands`'s key — 101/102/103. Kept even when `ageName` resolves it, so an unresolved
   * lookup can still render `UnresolvedIdentifier` (§3.1). */
  technologyId: number
  /** Resolved via reference data at the presentation boundary (Feudal/Castle/Imperial Age) — `null`
   * or absent renders `UnresolvedIdentifier` instead of a guess (§3.1, §3.2). */
  ageName?: ReactNode | null
  /** `age_up_commands`'s value — the research *command* time, in `world_time_ms`. */
  timeMs: number
}

export interface BuildEventData {
  id: string
  buildingId: number
  buildingName?: ReactNode | null
  timeMs: number
}

export interface TrainingEventData {
  id: string
  unitId: number
  unitName?: ReactNode | null
  /** `TrainingEvent.amount` — a `DeQueue` command can queue more than one at a time (§2.1). */
  amount: number
  timeMs: number
}

export interface ResearchEventData {
  id: string
  technologyId: number
  technologyName?: ReactNode | null
  timeMs: number
}

export interface AnalysisParticipantData {
  id: string
  alias: ReactNode
  civId: number | null
  civName?: ReactNode | null
  /** Rounded to the nearest whole number by this component (§2.1) — pass the raw
   * `actions_per_minute` figure. */
  apm: number
  actions: number
  villagersOrdered: number
  /** Chronological, oldest first — this component performs no sorting or deduplication of its own
   * (§3.1). */
  ageUps: AgeUpEventData[]
  builds: BuildEventData[]
  trainings: TrainingEventData[]
  researches: ResearchEventData[]
  /** `null` (or absent) renders no `ResignedLine` at all — never a placeholder (§2.1). */
  resignedAtMs?: number | null
}

export interface AnalysisTeamGroupData {
  id: string
  participants: AnalysisParticipantData[]
}

export interface AnalysisTimelineProps {
  /** The match-detail response has not carried an `analysis` object yet (§5 "loading") — a real
   * fact about the page, distinct from `state: "queued" | "running"`, which are facts about a known
   * analysis. Takes priority over every other prop. */
  loading?: boolean
  /** A network failure loading the match-detail response itself (§5 "error") — not any of the six
   * domain states this component otherwise renders. Takes priority over `state`. */
  error?: boolean
  onRetryLoad?: () => void
  state?: AnalysisState
  /** Only meaningful while `state === "published"` (§3.3, §3.4). */
  stale?: boolean
  engineName?: ReactNode
  engineVersion?: ReactNode
  /** Pre-formatted, matching every other date label in this system
   * (`match-history.md`'s own `playedAtLabel`). */
  analysedAtLabel?: ReactNode
  teams?: AnalysisTeamGroupData[]
  /** `state === "failed"` only — the failure class `apps/analyzer` recorded, never a traceback
   * (§3.5). */
  errorClass?: string
  /** Fires `POST /api/analyze` — the identical action behind `stale`'s "Recompute" and `refused`'s
   * "Try requesting analysis" (§3.4, §3.5). */
  onRequestAnalysis?: () => void
  /** True while a just-fired `onRequestAnalysis` is in flight — moves the button that fired it to
   * its own `loading` state (§3.4: "Recomputing…"). */
  requesting?: boolean
  className?: string
}

const HEADING_TEXT = 'Match analysis'

// §2.1 "every time value ... renders as m:ss — minutes unpadded, seconds zero-padded, floored from
// world_time_ms (never rounded up, so a row never claims an order happened before it did)".
function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function TimeValue({ ms }: { ms: number }) {
  return <span className="font-mono">{formatTime(ms)}</span>
}

function ResolvedOrUnresolved({
  label,
  id,
  name,
}: {
  label: string
  id: number
  name?: ReactNode | null
}) {
  if (name != null) {
    return <span className="text-text-primary">{name}</span>
  }
  return <UnresolvedIdentifier label={label} id={id} />
}

// §3.1's own normative copy: "`<Age name>` ordered — `<m:ss>`", never "reached".
function AgeUpList({ items }: { items: AgeUpEventData[] }) {
  const labelId = useId()
  return (
    <ListSection labelId={labelId} label="Age ups">
      {items.map((item) => (
        <li key={item.id}>
          <ResolvedOrUnresolved label="Technology" id={item.technologyId} name={item.ageName} />{' '}
          ordered — <TimeValue ms={item.timeMs} />
        </li>
      ))}
    </ListSection>
  )
}

function BuildOrderList({ items }: { items: BuildEventData[] }) {
  const labelId = useId()
  return (
    <ListSection labelId={labelId} label="Build order">
      {items.map((item) => (
        <li key={item.id}>
          <ResolvedOrUnresolved label="Building" id={item.buildingId} name={item.buildingName} /> —{' '}
          <TimeValue ms={item.timeMs} />
        </li>
      ))}
    </ListSection>
  )
}

function TrainingOrderList({ items }: { items: TrainingEventData[] }) {
  const labelId = useId()
  return (
    <ListSection labelId={labelId} label="Training order">
      {items.map((item) => (
        <li key={item.id}>
          <span className="font-mono">{item.amount}×</span>{' '}
          <ResolvedOrUnresolved label="Unit" id={item.unitId} name={item.unitName} /> —{' '}
          <TimeValue ms={item.timeMs} />
        </li>
      ))}
    </ListSection>
  )
}

// §2.1: excludes technology ids 101/102/103 — the caller's job (this component renders the list it
// is given), not this component's own filtering.
function ResearchList({ items }: { items: ResearchEventData[] }) {
  const labelId = useId()
  return (
    <ListSection labelId={labelId} label="Research">
      {items.map((item) => (
        <li key={item.id}>
          <ResolvedOrUnresolved
            label="Technology"
            id={item.technologyId}
            name={item.technologyName}
          />{' '}
          — <TimeValue ms={item.timeMs} />
        </li>
      ))}
    </ListSection>
  )
}

// §9: "each list ... is an <ol> — order is the fact being shown". `mt-4` on every instance gives
// both "SummaryStats to AgeUpList" and "between lists" the same §7 step (space-4).
function ListSection({
  labelId,
  label,
  children,
}: {
  labelId: string
  label: string
  children: ReactNode
}) {
  return (
    <div className="mt-4">
      <p id={labelId} className="font-sans text-sm font-semibold text-text-secondary">
        {label}
      </p>
      <ol aria-labelledby={labelId} className="mt-2 flex flex-col gap-1 font-sans text-sm">
        {children}
      </ol>
    </div>
  )
}

function ParticipantCivilisation({
  civId,
  civName,
}: {
  civId: number | null
  civName?: ReactNode | null
}) {
  if (civName != null) {
    return <span className="font-sans text-sm text-text-primary">{civName}</span>
  }
  if (civId != null) {
    return <UnresolvedIdentifier label="Civilisation" id={civId} />
  }
  return null
}

// §2.1: "Villagers ordered", never "Villagers trained", never "Villagers" (FR-043b) — the caveat
// line is present in every rendering, not only the first.
const VILLAGERS_ORDERED_CAVEAT =
  'Training commands, net of cancelled orders — not a population count.'

function ParticipantTimelineColumn({ participant }: { participant: AnalysisParticipantData }) {
  const headingId = useId()

  return (
    <article
      aria-labelledby={headingId}
      className="flex flex-col rounded-lg border border-border p-4"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <h4 id={headingId} className="font-sans text-lg font-semibold text-text-primary">
            {participant.alias}
          </h4>
          <ParticipantCivilisation civId={participant.civId} civName={participant.civName} />
        </div>
        <div className="mt-2 flex flex-wrap gap-4 md:mt-0">
          <StatValue
            variant="compact"
            label="Actions per minute"
            value={String(Math.round(participant.apm))}
          />
          <StatValue variant="compact" label="Actions" value={String(participant.actions)} />
          <StatValue
            variant="compact"
            label="Villagers ordered"
            value={String(participant.villagersOrdered)}
            secondaryLine={VILLAGERS_ORDERED_CAVEAT}
          />
        </div>
      </div>

      {participant.ageUps.length > 0 && <AgeUpList items={participant.ageUps} />}
      {participant.builds.length > 0 && <BuildOrderList items={participant.builds} />}
      {participant.trainings.length > 0 && <TrainingOrderList items={participant.trainings} />}
      {participant.researches.length > 0 && <ResearchList items={participant.researches} />}
      {participant.resignedAtMs != null && (
        <p className="mt-3 font-sans text-sm text-text-secondary">
          Resigned at <TimeValue ms={participant.resignedAtMs} />
        </p>
      )}
    </article>
  )
}

// §8: 375 stacks every column full-width; 768 pairs two columns from the same team; 1280 widens
// with the page — one card per participant at every width, never a `<table>` (§8's own reasoning).
function ParticipantColumns({ teams }: { teams: AnalysisTeamGroupData[] }) {
  const isTwoColumn = useBreakpoint('md')

  return (
    <div className="mt-4 flex flex-col gap-6">
      {teams.map((team) => (
        <div
          key={team.id}
          className={cx('flex flex-col gap-6', isTwoColumn && 'grid grid-cols-2 gap-6')}
        >
          {team.participants.map((participant) => (
            <ParticipantTimelineColumn key={participant.id} participant={participant} />
          ))}
        </div>
      ))}
    </div>
  )
}

// §3.4: a single inline `Badge` + `Button` — deliberately never a `Callout`, so a stale analysis
// never reads as a warning that hides the result (FR-041).
function StaleRecomputeNotice({
  onRequestAnalysis,
  requesting,
}: {
  onRequestAnalysis?: () => void
  requesting?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Badge variant="info">Newer analysis engine available</Badge>
      <Button
        variant="secondary"
        size="lg"
        loading={requesting}
        loadingLabel="Recomputing…"
        onClick={onRequestAnalysis}
      >
        Recompute
      </Button>
    </div>
  )
}

function AnalysisProgress({ state }: { state: 'queued' | 'running' }) {
  const label = state === 'queued' ? 'Waiting to start…' : 'Analysing this match…'
  return (
    <div aria-busy="true">
      <p className="font-sans text-sm text-text-secondary">{label}</p>
      <div className="mt-4 flex flex-col gap-3">
        <Skeleton variant="block" className="h-40 w-full rounded-lg" />
        <Skeleton variant="block" className="h-40 w-full rounded-lg" />
      </div>
    </div>
  )
}

// §3.5's own table — exact copy, never shared between the three shapes.
const FAILURE_COPY: Record<
  'failed' | 'unavailable' | 'refused',
  { tone: CalloutTone; heading: string; body: string }
> = {
  failed: {
    tone: 'danger',
    heading: 'This match could not be analysed',
    body: 'The recorded game could not be parsed.',
  },
  unavailable: {
    tone: 'danger',
    heading: 'Analysis is not available for this match',
    body: "This match's recorded game is no longer available, and it was never analysed. It cannot be analysed now.",
  },
  refused: {
    tone: 'warning',
    heading: 'Analysis is temporarily unavailable',
    body: 'This service has reached its limit for the number of recordings it can keep for analysis right now. Try again later.',
  },
}

function AnalysisFailureNotice({
  state,
  errorClass,
  onRequestAnalysis,
  requesting,
  className,
}: {
  state: 'failed' | 'unavailable' | 'refused'
  errorClass?: string
  onRequestAnalysis?: () => void
  requesting?: boolean
  className?: string
}) {
  const copy = FAILURE_COPY[state]
  // `Callout`'s own tone-to-role mapping (`shared-primitives.md`, `Callout.test.tsx`) gives
  // `role="alert"` to `danger` (`failed`, `unavailable`) and `role="status"` to `warning`
  // (`refused`) — the mapping every other spec in `specs/` cites and the one actually implemented.
  return (
    <Callout
      tone={copy.tone}
      // Occupies the same outline position "Match analysis" would have (h3) — neither of these
      // three states renders that heading (§3's own table), so the Callout's heading takes its
      // place rather than nesting one level deeper.
      headingLevel={3}
      heading={copy.heading}
      className={className}
      actions={
        state === 'refused' ? (
          <Button
            variant="secondary"
            size="lg"
            loading={requesting}
            loadingLabel="Requesting…"
            onClick={onRequestAnalysis}
          >
            Try requesting analysis
          </Button>
        ) : undefined
      }
    >
      <p>{copy.body}</p>
      {state === 'failed' && errorClass && (
        <p className="font-mono text-xs text-text-secondary">Error: {errorClass}</p>
      )}
    </Callout>
  )
}

/** The factual, per-participant account of a match once someone has asked for it to be analysed —
 * what they built, trained, researched and ordered, and when. See
 * `packages/design-system/specs/analysis-timeline.md`. */
export function AnalysisTimeline({
  loading = false,
  error = false,
  onRetryLoad,
  state,
  stale = false,
  engineName,
  engineVersion,
  analysedAtLabel,
  teams = [],
  errorClass,
  onRequestAnalysis,
  requesting = false,
  className,
}: AnalysisTimelineProps) {
  const headingId = useId()

  if (error) {
    return (
      <Callout
        tone="danger"
        headingLevel={3}
        heading="We could not load this match's analysis. Try again."
        actions={
          <Button variant="primary" size="lg" onClick={onRetryLoad}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  // §5 "loading" — the ordinary "the page has not loaded yet" case, not to be confused with the
  // `queued`/`running` domain state below.
  if (loading || !state) {
    return (
      <section aria-labelledby={headingId} className={className} aria-busy="true">
        <h3 id={headingId} className="font-display text-xl font-semibold text-text-primary">
          {HEADING_TEXT}
        </h3>
        <div className="mt-4 flex flex-col gap-3">
          <Skeleton variant="block" className="h-40 w-full rounded-lg" />
          <Skeleton variant="block" className="h-40 w-full rounded-lg" />
        </div>
      </section>
    )
  }

  // §3's table: none of the three failure shapes renders the "Match analysis" heading — the
  // Callout's own heading occupies that position instead (AnalysisFailureNotice, above).
  if (state === 'failed' || state === 'unavailable' || state === 'refused') {
    return (
      <AnalysisFailureNotice
        state={state}
        errorClass={errorClass}
        onRequestAnalysis={onRequestAnalysis}
        requesting={requesting}
        className={className}
      />
    )
  }

  if (state === 'queued' || state === 'running') {
    return (
      <section aria-labelledby={headingId} className={className}>
        <h3 id={headingId} className="font-display text-xl font-semibold text-text-primary">
          {HEADING_TEXT}
        </h3>
        <div className="mt-4">
          <AnalysisProgress state={state} />
        </div>
      </section>
    )
  }

  // state === 'published'
  return (
    <section aria-labelledby={headingId} className={className}>
      <div className="flex flex-col gap-3">
        <h3 id={headingId} className="font-display text-xl font-semibold text-text-primary">
          {HEADING_TEXT}
        </h3>
        {/* §3.4: present only while stale — never rendered-and-disabled otherwise. */}
        {stale && (
          <StaleRecomputeNotice onRequestAnalysis={onRequestAnalysis} requesting={requesting} />
        )}
      </div>
      <p className="mt-1 font-sans text-xs text-text-secondary">
        Analysed with {engineName} {engineVersion} on {analysedAtLabel}.
      </p>
      <ParticipantColumns teams={teams} />
    </section>
  )
}
