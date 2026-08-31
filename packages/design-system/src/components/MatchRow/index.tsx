import { Fragment, type ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { CaptureStateBadge } from '../CaptureStateBadge'
import { CivilisationIcon } from '../CivilisationIcon'
import { MapThumbnail } from '../MapThumbnail'
import { PlayerColourSwatch } from '../PlayerColourSwatch'
import { Skeleton } from '../Skeleton'
import type { StatValueDelta } from '../StatValue'

// packages/design-system/specs/match-history.md, widened by §12 (004, US1)

/** Shared by `MatchRow.outcome` and `MatchDetailPanel`'s `ParticipantData.result` (imported there
 * from here, mirroring how both components already share `StatValueDelta` from `StatValue`) —
 * `"unknown"` is not a fallback spelling of `"loss"`: it is the state a `result` this service has
 * not yet recorded (`match_players.result` is `null` for every row today — `discover.py`'s own
 * docstring) must render as, per match-history.md §2a. `apps/web/src/features/matches/format.ts`'s
 * `formatOutcome` is the one place a wire `result` becomes this union. */
export type MatchOutcome = 'win' | 'loss' | 'unknown'

/** A participant's own recorded result, exactly as the wire sends it (`"win" | "loss" | null`) —
 * distinct from `MatchOutcome`, which is this row's own three-state read of *the viewed profile's*
 * result (§2a). Feeds §12.3's `TeamResult` marker, computed per group from every member's own
 * result, and is never rendered per participant on this row (§12.3's own "what the row
 * deliberately does not show"). */
export type MatchParticipantResult = 'win' | 'loss' | null

export interface MatchRowParticipant {
  /** Wire `profile_id` — a stable React key, never rendered. */
  profileId: string | number
  alias: string
  /** `match_players.team_id` for this participant. `null` groups with any other `null`-team
   * participant into a trailing, un-numbered group (§12.3). */
  teamId: number | null
  /** `undefined`/`null`/out-of-range all resolve to `PlayerColourSwatch`'s own neutral chip —
   * passed straight through, never re-interpreted here (FR-003, FR-010). */
  colorId?: number | null
  /** `null` is FR-004's neutral state, never a loss. */
  result: MatchParticipantResult
  /** Marks the one participant who is the profile whose history this row belongs to — used only
   * to order this participant, and their team, first (§12.3 "Ordering"). **Never rendered**: no
   * participant is ever visually marked "you" (§11.1's rule, extended here). */
  isViewer?: boolean
}

export interface MatchRowData {
  gameId: string
  /** The match detail route (T076's `matches.$gameId.tsx`). `MatchRow` never invents this path. */
  href: string
  outcome: MatchOutcome
  /** §12.3's `Participants` field, replacing §4's single-opponent treatment (superseded, §12.2).
   * **Absent** — never an empty array — for a row whose participant columns are not yet projected
   * (§12.6): the field is omitted entirely, never rendered as an empty "vs". */
  participants?: MatchRowParticipant[]
  /** `matches.map_name` verbatim. `null` renders `MapThumbnail`'s own unresolved-name treatment
   * (§11.2, via that component). */
  map: string | null
  /** The viewed profile's own civilisation name, composed into `CivilisationIcon`'s `name`
   * (§12.2: "mark + name, the name never suppressed"). */
  civilisation: ReactNode
  /** `packages/game-assets`' `civilisationIcon(civName)` result, resolved by the caller —
   * `undefined` when the pack does not cover it (§12.1 rule 3, FR-010). This component never
   * imports the pack and never builds this URL itself. */
  civIconUrl?: string
  /** `packages/game-assets`' `mapThumbnail(mapName)` result, resolved by the caller — `undefined`
   * for any map the pack does not cover (§12.1 rule 3, FR-002, FR-010). */
  mapThumbnailUrl?: string
  /** FR-006: the ladder name, joining `Map` as a second `xs` `text-secondary` line at 375/768
   * only — never a ninth column at 1280 (§12.4's own reasoning). */
  leaderboardName?: ReactNode
  /** The viewed profile's absolute rating, post-match. `null`/absent together with no
   * `ratingChange` renders no rating field at all (§12.4's table) — never a `–`, never a `0`. */
  rating?: number | null
  /** The signed rating change. `value: 0` is a real, reported movement (renders `(0)`, neutral
   * tone, no sign character) and is not the same fact as `undefined` ("not known" — no
   * parenthetical at all, §12.4). */
  ratingChange?: StatValueDelta
  /** Pre-formatted — "34 min", never raw seconds (§2). */
  durationLabel: ReactNode
  /** Pre-formatted relative time — "3 hours ago" (§2). */
  playedAtRelative: ReactNode
  /** Absolute date/time, shown on hover/focus via the native `title` tooltip (§2). */
  playedAtAbsolute?: string
  captureStatus?: string | null
  captureDeadlineAt?: string | null
}

export interface MatchRowProps {
  match: MatchRowData
  /** Wires this row's click into the caller's own router (T388), the same seam
   * `PlayerResultRow.onNavigate` defines — the row stays a real `<a href={match.href}>`, a
   * modified click or the absence of `onNavigate` falls through to native handling. */
  onNavigate?: (href: string) => void
  className?: string
}

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring'

// match-history.md §2a: "Win"/"Loss" assert a fact this service has; "Unknown" (`text-secondary`,
// never `success`/`danger`) is the one state that does not, and reads as a gap by wording alone —
// never colour alone (constitution VI).
const OUTCOME_LABEL_TEXT: Record<MatchOutcome, string> = {
  win: 'Win',
  loss: 'Loss',
  unknown: 'Unknown',
}

const OUTCOME_LABEL_TONE: Record<MatchOutcome, string> = {
  win: 'text-success',
  loss: 'text-danger',
  unknown: 'text-secondary',
}

function OutcomeLabel({ outcome }: { outcome: MatchOutcome }) {
  return (
    <span className={cx('font-sans text-sm font-semibold', OUTCOME_LABEL_TONE[outcome])}>
      {OUTCOME_LABEL_TEXT[outcome]}
    </span>
  )
}

// --- §12.3: Participants, grouped by side, each in their colour --------------------------------

interface ParticipantGroup {
  teamId: number | null
  members: MatchRowParticipant[]
}

/** Moves the viewed profile to the front of their own group (§12.3 "inside a group, the viewed
 * profile first, then the order the API returned"). A group with no flagged member is left in the
 * order it was given. */
function orderMembers(members: MatchRowParticipant[]): MatchRowParticipant[] {
  const viewerIndex = members.findIndex((member) => member.isViewer)
  if (viewerIndex <= 0) return members
  const [viewer] = members.splice(viewerIndex, 1)
  return [viewer, ...members]
}

/** Groups by `team_id`; the viewed profile's own group leads, then the rest ascending by
 * `team_id` (a `null` team trails every numbered one) — §12.3 "Ordering", never a caller-relative
 * perspective beyond this (§11.3, §11.1's point 1). */
function groupByTeam(participants: MatchRowParticipant[]): ParticipantGroup[] {
  const byTeam = new Map<number | null, MatchRowParticipant[]>()
  for (const participant of participants) {
    const existing = byTeam.get(participant.teamId)
    if (existing) {
      existing.push(participant)
    } else {
      byTeam.set(participant.teamId, [participant])
    }
  }

  const viewer = participants.find((participant) => participant.isViewer)
  const viewerTeamId = viewer ? viewer.teamId : undefined

  const rest = [...byTeam.keys()].filter((teamId) => teamId !== viewerTeamId)
  rest.sort((a, b) => {
    if (a === null) return 1
    if (b === null) return -1
    return a - b
  })
  const ordered = viewerTeamId !== undefined ? [viewerTeamId, ...rest] : rest

  return ordered.map((teamId) => ({
    teamId,
    members: orderMembers([...(byTeam.get(teamId) ?? [])]),
  }))
}

/** Exported for `MatchDetailPanel` (T431), which computes the identical marker for its own
 * `TeamGroup` heading from the same three-state result — one answer to "did this side win", never
 * two (match-history.md §12.5's own "never re-implements one"). */
export type TeamResultKind = 'won' | 'lost' | 'unknown-result' | null

/** §12.3's `TeamResult` marker table: every member's own `result` decides one of three words, or
 * — for the mixed case the table calls "should not occur; possible mid-backfill" — no marker at
 * all, never a guess. Typed over the bare `result` field, not the full `MatchRowParticipant`, so
 * `MatchDetailPanel`'s own `ParticipantData` (a different shape, sharing only this one field) can
 * reuse it without re-deriving the table (T431). */
export function computeTeamResult(members: { result: MatchParticipantResult }[]): TeamResultKind {
  if (members.every((member) => member.result === 'win')) return 'won'
  if (members.every((member) => member.result === 'loss')) return 'lost'
  if (members.every((member) => member.result === null)) return 'unknown-result'
  return null
}

const TEAM_RESULT_TEXT: Record<Exclude<TeamResultKind, null>, string> = {
  won: 'Won',
  lost: 'Lost',
  'unknown-result': 'Result unknown',
}

const TEAM_RESULT_TONE: Record<Exclude<TeamResultKind, null>, string> = {
  won: 'text-success',
  lost: 'text-danger',
  'unknown-result': 'text-secondary',
}

/** Exported alongside `computeTeamResult` for the same reason (T431). */
export function TeamResultMarker({ kind }: { kind: TeamResultKind }) {
  if (kind == null) return null
  return (
    <span className={cx('font-sans text-sm font-semibold', TEAM_RESULT_TONE[kind])}>
      {TEAM_RESULT_TEXT[kind]}
    </span>
  )
}

function ParticipantChip({ participant }: { participant: MatchRowParticipant }) {
  return (
    <span className="inline-flex items-center gap-2">
      <PlayerColourSwatch colorId={participant.colorId} playerName={participant.alias} size="xs" />
      <span className="font-sans text-sm text-text-primary">{participant.alias}</span>
    </span>
  )
}

/** §12.3's cap: up to `cap` members per group, in order; the remainder is `"and N others"` —
 * never a bare count, never a dead end (the whole row is already one link to the match detail,
 * §9, where `MatchDetailPanel` names everyone, FR-011). */
function ParticipantGroupView({ group, cap }: { group: ParticipantGroup; cap: number }) {
  const shown = group.members.slice(0, cap)
  const overflow = group.members.length - shown.length
  return (
    <span className="inline-flex flex-wrap items-center gap-3">
      <TeamResultMarker kind={computeTeamResult(group.members)} />
      {shown.map((participant) => (
        <ParticipantChip key={participant.profileId} participant={participant} />
      ))}
      {overflow > 0 && (
        <span className="font-sans text-sm text-text-secondary">and {overflow} others</span>
      )}
    </span>
  )
}

/** §12.3's `Participants` field. `cap` is 3 in the card layout and 2 in the 1280 table, where the
 * column's width is bounded by the table rather than by the window (§12.7). */
function Participants({ participants, cap }: { participants: MatchRowParticipant[]; cap: number }) {
  const groups = groupByTeam(participants)

  if (groups.length > 2) {
    // §12.3: more than two groups (a free-for-all) — no grouping and no "vs": the viewed
    // profile's own swatch and alias, then "and N others" for everyone else.
    const viewer = participants.find((participant) => participant.isViewer) ?? participants[0]
    const othersCount = participants.length - 1
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <ParticipantChip participant={viewer} />
        {othersCount > 0 && (
          <span className="font-sans text-sm text-text-secondary">and {othersCount} others</span>
        )}
      </span>
    )
  }

  return (
    <span className="flex flex-wrap items-center gap-3">
      {groups.map((group, index) => (
        <Fragment key={group.teamId ?? 'no-team'}>
          {index > 0 && <span className="font-sans text-sm text-text-secondary">vs</span>}
          <ParticipantGroupView group={group} cap={cap} />
        </Fragment>
      ))}
    </span>
  )
}

// --- §12.4: rating and its movement --------------------------------------------------------------

// U+2212 MINUS SIGN, not a hyphen — aligns with digits in a monospaced face and a screen reader
// says "minus" rather than swallowing it (§12.4).
const MINUS_SIGN = '−'

function ratingSign(value: number): string {
  if (value > 0) return '+'
  if (value < 0) return MINUS_SIGN
  return ''
}

function ratingTone(value: number): string {
  if (value > 0) return 'text-success'
  if (value < 0) return 'text-danger'
  return 'text-secondary'
}

function ratingMagnitude(delta: StatValueDelta): string {
  return delta.formatted ?? String(Math.abs(delta.value))
}

/** §12.4's format table: `922 (+16)`, `921 (−15)`, `922 (0)` (a reported zero movement, neutral
 * tone, no sign), `922` alone (`rating_diff` not known — never `(+0)`, never `(—)`), or nothing at
 * all (both absent). The sign is always a character in the text, never colour alone (§12.1 rule
 * 2), and never animates on entry (`StatValue`'s own rule, README rule 1). Exported: `§12.5`
 * requires `MatchDetailPanel`'s own rating figure to follow "identical rules" — reused rather than
 * re-derived (T431), so the list and the detail view cannot drift on this format. */
export function RatingFigure({
  rating,
  ratingChange,
  size,
}: {
  rating?: number | null
  ratingChange?: StatValueDelta
  size: 'md' | 'sm'
}) {
  if (rating == null && !ratingChange) return null

  const textSize = size === 'md' ? 'text-md' : 'text-sm'

  if (rating == null && ratingChange) {
    // Not reachable per data-model.md (`rating_diff` is `null` whenever `rating` is missing), but
    // the spec names the render explicitly: the change alone, never an empty parenthesis.
    return (
      <span
        className={cx(
          'font-mono font-semibold tracking-tight',
          textSize,
          ratingTone(ratingChange.value),
        )}
      >
        {ratingSign(ratingChange.value)}
        {ratingMagnitude(ratingChange)}
      </span>
    )
  }

  return (
    <span className={cx('font-mono font-semibold tracking-tight text-text-primary', textSize)}>
      {rating}
      {ratingChange && (
        <>
          {' '}
          <span className={ratingTone(ratingChange.value)}>
            ({ratingSign(ratingChange.value)}
            {ratingMagnitude(ratingChange)})
          </span>
        </>
      )}
    </span>
  )
}

function MatchMeta({ match }: { match: MatchRowData }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-xs text-text-secondary">
      <span>{match.durationLabel}</span>
      <span aria-hidden="true">·</span>
      <span title={match.playedAtAbsolute}>{match.playedAtRelative}</span>
    </div>
  )
}

/** One match, the whole card is a single link (§2, §9): everything inside — including
 * `CaptureStateBadge`, `CivilisationIcon`, `MapThumbnail` and `PlayerColourSwatch` — is
 * non-interactive text and imagery, so the row has exactly one focus stop. Used directly below
 * `xl`; `MatchList` renders a real `<table>` above it instead (§8). */
export function MatchRow({ match, onNavigate, className }: MatchRowProps) {
  return (
    <a
      href={match.href}
      onClick={createRowLinkClickHandler(match.href, onNavigate)}
      className={cx(
        'flex flex-col gap-2 rounded-lg border border-border bg-surface p-4',
        'transition-colors duration-120 ease-standard hover:bg-surface-sunken',
        focusRing,
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <OutcomeLabel outcome={match.outcome} />
        <RatingFigure rating={match.rating} ratingChange={match.ratingChange} size="md" />
      </div>

      <div className="flex flex-col gap-1">
        <MapThumbnail thumbnailUrl={match.mapThumbnailUrl} mapName={match.map} size="md" />
        {match.leaderboardName != null && (
          <span className="font-sans text-xs text-text-secondary">{match.leaderboardName}</span>
        )}
      </div>

      <CivilisationIcon iconUrl={match.civIconUrl} name={match.civilisation} size="md" />

      {/* §12.6: absent, never an empty "vs", for a row whose participant columns are not yet
       * projected. */}
      {match.participants && match.participants.length > 0 && (
        <Participants participants={match.participants} cap={3} />
      )}

      <MatchMeta match={match} />
      <CaptureStateBadge
        context="compact"
        captureStatus={match.captureStatus}
        captureDeadlineAt={match.captureDeadlineAt}
      />
    </a>
  )
}

export type MatchListStatus = 'default' | 'loading' | 'error' | 'empty'

/** match-history.md §11.3: which player's history this list is — the row itself never differs
 * (`MatchRow` above takes no `subject` of its own), only the two fixed strings around it that
 * presuppose the viewer is the subject: the table's own `<caption>` and the empty-state sentence.
 * Mirrors `ProfileSummarySubject` (`ProfileSummary`), the identical read this component's own page
 * header already uses for the header above this list. */
export type MatchListSubject = 'self' | 'other'

export interface MatchListProps {
  status?: MatchListStatus
  matches?: MatchRowData[]
  onRetry?: () => void
  /** Forwarded, unchanged, to every `MatchRow` in the card layout and every row link in the table
   * layout (T388) — see `MatchRowProps.onNavigate`. */
  onNavigate?: (href: string) => void
  /** Defaults to `'self'`, preserving this component's original copy unchanged for
   * `matches.index.tsx` (T075) — the caller's own history. `'other'` swaps §11.3's two strings for
   * a third party's, read from `subjectAlias`. */
  subject?: MatchListSubject
  /** The viewed player's alias, spliced into §11.3's two `subject="other"` strings. A plain
   * `string`, not `ReactNode` — one of these two strings is also this component's own `<ul>`
   * `aria-label` (§9's accessible list name), which cannot take a JSX child. Ignored for
   * `subject="self"` (default), and never required there — the caller's own list names no alias
   * in either string it uses. */
  subjectAlias?: string
  className?: string
}

/** The list of matches: reverse-chronological, one DOM per viewport (never both a table and a
 * card list at once — §8), plus the list's own loading/error/empty states (§5). Consumed by
 * `apps/web/src/routes/matches.index.tsx` (T075), which supplies the page header above it. */
export function MatchList({
  status = 'default',
  matches = [],
  onRetry,
  onNavigate,
  subject = 'self',
  subjectAlias,
  className,
}: MatchListProps) {
  // §8 reserves everything below 1280 for cards; `xl` is the named breakpoint at that width
  // (`lg` is 1024 — see `useMediaQuery.ts`'s own DS-5 table), not `lg`.
  const isTable = useBreakpoint('xl')

  // §11.3: the one fixed string that presupposes the viewer is the subject, computed once here
  // rather than at each of its two call sites below — the table `<caption>` and the `<ul>`'s own
  // `aria-label` (§9, §11.5: "screen-reader users get the corrected subject the same way sighted
  // users do, from the same string").
  const caption = subject === 'other' ? `${subjectAlias}'s recent matches` : 'Your recent matches'

  if (status === 'loading') {
    return (
      <div className={cx('flex flex-col gap-3', className)} aria-busy="true">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} variant="block" className="h-24 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <Callout
        tone="danger"
        heading="We could not load your match history"
        actions={
          <Button variant="primary" size="lg" onClick={onRetry}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  if (status === 'empty' || matches.length === 0) {
    // §11.3: "the empty state is a fact about the player, stated once" — a single sentence for
    // `subject="other"`, never the first-person heading+body pair `subject="self"` keeps below.
    if (subject === 'other') {
      return (
        <Callout
          tone="info"
          heading={`${subjectAlias} has no matches in their history yet.`}
          className={className}
        />
      )
    }
    return (
      <Callout tone="info" heading="No matches yet" className={className}>
        Once you play, they will appear here.
      </Callout>
    )
  }

  if (isTable) {
    return (
      <MatchTable
        matches={matches}
        onNavigate={onNavigate}
        caption={caption}
        className={className}
      />
    )
  }

  return (
    <ul className={cx('flex flex-col gap-3', className)} aria-label={caption}>
      {matches.map((match) => (
        <li key={match.gameId}>
          <MatchRow match={match} onNavigate={onNavigate} />
        </li>
      ))}
    </ul>
  )
}

function MatchTable({
  matches,
  onNavigate,
  caption,
  className,
}: {
  matches: MatchRowData[]
  onNavigate?: (href: string) => void
  caption: string
  className?: string
}) {
  return (
    <table className={cx('w-full border-collapse text-left font-sans text-sm', className)}>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-border">
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Result
          </th>
          {/* §12.7 renames this column from "Opponent" to "Players" — both sides now name
           * participants, not just the opponent. */}
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Players
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Map
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            Civilisation
          </th>
          {/* §12.7 renames this column from "Change" to "Rating" — it now carries the absolute
           * value alongside the signed change. */}
          <th scope="col" className="py-3 pr-5 text-right font-normal text-text-secondary">
            Rating
          </th>
          <th scope="col" className="py-3 pr-5 text-right font-normal text-text-secondary">
            Duration
          </th>
          <th scope="col" className="py-3 pr-5 font-normal text-text-secondary">
            When
          </th>
          <th scope="col" className="py-3 font-normal text-text-secondary">
            Capture
          </th>
        </tr>
      </thead>
      <tbody>
        {matches.map((match) => (
          <MatchTableRow key={match.gameId} match={match} onNavigate={onNavigate} />
        ))}
      </tbody>
    </table>
  )
}

// A `<tr>` cannot itself be an `<a>`, so the row's single link lives in one cell and is stretched
// over the whole row with `after:absolute after:inset-0` against the row's own `relative` — the
// standard "one link, whole row clickable" technique, keeping exactly one focus stop (§9).
function MatchTableRow({
  match,
  onNavigate,
}: {
  match: MatchRowData
  onNavigate?: (href: string) => void
}) {
  return (
    <tr className="group relative border-b border-border transition-colors duration-120 ease-standard hover:bg-surface-sunken">
      <th scope="row" className="py-3 pr-5 font-normal">
        <a
          href={match.href}
          onClick={createRowLinkClickHandler(match.href, onNavigate)}
          className={cx(
            'static font-sans text-sm font-semibold after:absolute after:inset-0',
            focusRing,
            OUTCOME_LABEL_TONE[match.outcome],
          )}
        >
          {OUTCOME_LABEL_TEXT[match.outcome]}
        </a>
      </th>
      <td className="py-3 pr-5 text-text-primary">
        {/* §12.7: the Players column names at most two participants per side before its overflow
         * text — the column's width is bounded by the table, not by the window. */}
        {match.participants && match.participants.length > 0 && (
          <Participants participants={match.participants} cap={2} />
        )}
      </td>
      <td className="py-3 pr-5 text-text-primary">
        {/* §12.7: `sm` (32px) here so a row with a thumbnail and a row without one are the same
         * height — map-thumbnail.md §3's own reason for this size existing. */}
        <MapThumbnail thumbnailUrl={match.mapThumbnailUrl} mapName={match.map} size="sm" />
      </td>
      <td className="py-3 pr-5 text-text-primary">
        <CivilisationIcon iconUrl={match.civIconUrl} name={match.civilisation} size="md" />
      </td>
      <td className="py-3 pr-5 text-right">
        <RatingFigure rating={match.rating} ratingChange={match.ratingChange} size="sm" />
      </td>
      <td className="py-3 pr-5 text-right font-mono text-text-primary">{match.durationLabel}</td>
      <td className="py-3 pr-5 text-text-secondary" title={match.playedAtAbsolute}>
        {match.playedAtRelative}
      </td>
      <td className="py-3">
        {/* `stacked`: this column's width is bounded by the table, not by the window
         * (match-history.md §8) — told to stack rather than left to infer a container width the
         * badge cannot observe (§8, capture-state-badge.md's own `stacked` prop). */}
        <CaptureStateBadge
          context="compact"
          stacked
          captureStatus={match.captureStatus}
          captureDeadlineAt={match.captureDeadlineAt}
        />
      </td>
    </tr>
  )
}
