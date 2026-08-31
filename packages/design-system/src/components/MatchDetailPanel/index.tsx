import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { CaptureStateBadge } from '../CaptureStateBadge'
import { CivilisationIcon } from '../CivilisationIcon'
import { MapThumbnail } from '../MapThumbnail'
import {
  computeTeamResult,
  type MatchOutcome,
  RatingFigure,
  type TeamResultKind,
  TeamResultMarker,
} from '../MatchRow'
import { PlayerColourSwatch } from '../PlayerColourSwatch'
import { Skeleton } from '../Skeleton'
import type { StatValueDelta } from '../StatValue'

// packages/design-system/specs/match-history.md §§1-11. §11 (003, US2) widens both components to
// any match this service holds (T327) and any player's history (T328) — see §11's own note on why
// no prop here ever marks a participant as "you" and why `CaptureStateBadge`/`DownloadAction` keep
// reading only the caller's own point of view. §12 (004, US1, T431) widens both further: game
// imagery and colour, composed from `CivilisationIcon`/`MapThumbnail`/`PlayerColourSwatch` (T429)
// and never re-implemented here — two presentations of the same fact are how the list and the
// detail view start disagreeing about a match.

export interface ParticipantData {
  id: string
  alias: ReactNode
  /** `GET /api/matches/{game_id}`'s own `civ_id` (`routers/matches.py`) — always present when the
   * match recorded a civilisation for this participant, `null` in the rare case it did not.
   * Carried separately from `civName` so an unresolved name can still show *this*. */
  civId: number | null
  /** Resolved civilisation name (`civilisation_name`, `apps/api/.../civilizations.py`) — `null`
   * only when this service's own reference data cannot name `civId` (FR-020, §11.2). Renders as
   * `UnresolvedIdentifier` rather than being filled in with `civId` as if it were a name. */
  civName: ReactNode | null
  /** `packages/game-assets`' `civilisationIcon(civName)` result, resolved by the caller —
   * `undefined` when the pack does not cover it (§12.1 rule 3, FR-010) or when `civName` itself is
   * `null` (§11.2's unresolved treatment takes over instead; `CivilisationIcon` is never composed
   * for that case). This component never imports the pack and never builds this URL itself. */
  civIconUrl?: string
  /** `match_players.color_id` after read-time enrichment (data-model.md §6). `undefined`/`null`/
   * out-of-range all resolve to `PlayerColourSwatch`'s own neutral chip — passed straight through,
   * never re-interpreted here (FR-003, FR-010). */
  colorId?: number | null
  /** `"unknown"` whenever this system has not recorded a result for this participant yet
   * (`match_players.result` is `null` for every row today — `discover.py`'s own docstring) —
   * never coerced to `"loss"`; renders as its own state, never as a false defeat (match-history.md
   * §2a). Shared with `MatchRow.outcome`, imported from that module. */
  result: MatchOutcome
  /** The viewed match's absolute rating for this participant, post-match — `null`/absent together
   * with no `ratingChange` renders no rating field at all (§12.4's table, reused verbatim via
   * `RatingFigure`) — never a `–`, never a `0`. */
  rating?: number | null
  /** Absent when the match carries no rating change to report for this participant. `value: 0` is
   * a real, reported movement (renders `(0)`, neutral tone) and is not the same fact as `undefined`
   * ("not known" — no parenthetical at all, §12.4). */
  ratingChange?: StatValueDelta
}

export interface TeamGroupData {
  id: string
  /** e.g. "Team 1". Named once and reused as both the visible heading and the table's own
   * visually hidden `<caption>` — never invented twice (§9). §12.3's `TeamResult` marker
   * ("Won"/"Lost"/"Result unknown") is computed from `participants` below and joins both, as
   * "Team 1 — Won" (§12.5); it is never a second field a caller must keep in sync by hand. */
  name: ReactNode
  participants: ParticipantData[]
}

export interface MatchDetailData {
  gameId: string
  /** `matches.map_name` verbatim (`routers/matches.py`) — `null` when the source gave none. Unlike
   * `civId`/`civName` this schema carries no separate numeric map identifier at all (`map_name`
   * *is* the raw value, per that router's own note), so a `null` map renders via
   * `UnresolvedIdentifier` with no id to show, never a fabricated one (§11.2). **Narrowed from
   * `ReactNode | null` to `string | null` by T431**: `MapThumbnail` (composed here, §12.5) takes
   * the map name as a plain string — the same type `matches.map_name` and every caller of this
   * field has always actually supplied. */
  map: string | null
  /** `packages/game-assets`' `mapThumbnail(mapName)` result, resolved by the caller — `undefined`
   * for any map the pack does not cover (§12.1 rule 3, FR-002, FR-010). Composed into
   * `MapThumbnail` at `lg` (§12.5); a `null` `map` shows no thumbnail regardless of this value —
   * nothing is ever guessed from a neighbouring match. */
  mapThumbnailUrl?: string
  leaderboardName: ReactNode
  /** Pre-formatted — "34 min", never raw seconds. */
  durationLabel: ReactNode
  /** Pre-formatted played-on date/time. */
  playedAtLabel: ReactNode
  /** FR-018's "game version" — `matches.patch` verbatim (§11.1 point 3). There is no
   * version-to-name table the way there is for civilisations and leaderboards, so this is never
   * subject to `UnresolvedIdentifier` treatment; it is plain text or absent. */
  gameVersion?: ReactNode | null
  captureStatus?: string | null
  captureDeadlineAt?: string | null
  teams: TeamGroupData[]
}

/** §11.2: an identifier this service's reference data cannot name, shown as itself rather than
 * filled in with a guess. Three signals, never colour alone: a label prefix that says "id," not a
 * name; `text-secondary` (one step down from a resolved name's `text-primary`); and `font-mono`,
 * the same treatment `ProfileSummary`'s `ProfileId` already gives every other bare identifier in
 * this system (DS-8). `id` is omitted only for `Map` (§11.1's own note: this schema carries no
 * separate numeric map identifier — `map_name` already *is* the raw value, and `null` means the
 * source sent none at all, not that a known id could not be named) — the wording still says so
 * rather than presenting an empty gap silently. */
export function UnresolvedIdentifier({ label, id }: { label: string; id?: number | string }) {
  return (
    <span className="font-mono text-sm text-text-secondary">
      {id === undefined ? `${label} — unresolved` : `${label} ID ${id}`}
    </span>
  )
}

/** §12.5: "Civilisation (CivilisationIcon lg, mark + name, or UnresolvedIdentifier)" — composes
 * `CivilisationIcon` (T429) for the resolved case rather than re-implementing mark+name rendering;
 * §11.2's unresolved treatment (a name this service's own reference data cannot give) is unchanged
 * and untouched by that component, which is never handed a `null` name to render its own generic
 * "Unknown civilisation" fallback for — the two absences are different facts (§11.2) and stay
 * distinguishable. `text-text-primary` is applied here, at the call site, because `CivilisationIcon`
 * itself inherits `currentColor` rather than setting one (civilisation-icon.md §5) — the same
 * pattern `MatchRow`'s own 1280 table column already uses for this mark. */
function ParticipantCivilisation({
  civId,
  civName,
  civIconUrl,
}: {
  civId: number | null
  civName: ReactNode
  civIconUrl?: string
}) {
  if (civName != null) {
    return (
      <CivilisationIcon
        iconUrl={civIconUrl}
        name={civName}
        size="lg"
        className="text-text-primary"
      />
    )
  }
  if (civId != null) {
    return <UnresolvedIdentifier label="Civilisation" id={civId} />
  }
  return null
}

export type MatchDetailStatus = 'default' | 'loading' | 'error' | 'not-found'
export type DownloadActionState = 'idle' | 'loading' | 'error'

export interface MatchDetailPanelProps {
  status?: MatchDetailStatus
  match?: MatchDetailData
  downloadState?: DownloadActionState
  onDownload?: () => void
  onRetry?: () => void
  /** Where "back to the match list" points. Defaults to `/matches` (T075's route). */
  matchListHref?: string
  className?: string
}

// match-history.md §2a: the same three-state treatment `MatchRow.OutcomeLabel` gives `outcome` —
// "Unknown" in `text-secondary`, never `success`/`danger`, never folded into "Loss".
const RESULT_LABEL_TEXT: Record<MatchOutcome, string> = {
  win: 'Win',
  loss: 'Loss',
  unknown: 'Unknown',
}

const RESULT_LABEL_TONE: Record<MatchOutcome, string> = {
  win: 'text-success',
  loss: 'text-danger',
  unknown: 'text-secondary',
}

function ResultLabel({ result }: { result: MatchOutcome }) {
  return (
    <span className={cx('font-sans text-sm font-semibold', RESULT_LABEL_TONE[result])}>
      {RESULT_LABEL_TEXT[result]}
    </span>
  )
}

/** Everything about one match, and the one action a `stored` replay is for. `status="loading"`
 * needs no `match` at all; every other status requires one. */
export function MatchDetailPanel({
  status = 'default',
  match,
  downloadState = 'idle',
  onDownload,
  onRetry,
  matchListHref = '/matches',
  className,
}: MatchDetailPanelProps) {
  if (status === 'error') {
    return (
      <Callout
        tone="danger"
        heading="We could not load this match"
        actions={
          <Button variant="primary" size="lg" onClick={onRetry}>
            Try again
          </Button>
        }
        className={className}
      />
    )
  }

  // "Not found" covers both an unknown game id and a real match that is not the caller's own —
  // the two must never be distinguishable to the caller (FR-045).
  if (status === 'not-found') {
    return (
      <Callout
        tone="danger"
        heading="This match could not be found."
        actions={
          <Button variant="secondary" size="lg" href={matchListHref}>
            Back to the match list
          </Button>
        }
        className={className}
      />
    )
  }

  if (status === 'loading' || !match) {
    return (
      <div className={cx('flex flex-col gap-6', className)} aria-busy="true">
        <header className="flex flex-col gap-2">
          <Skeleton variant="text" lines={1} className="w-48" />
          <Skeleton variant="text" lines={1} className="w-64" />
          {/* §11.6: GameVersion carries its own loading placeholder, extending §5's existing
           * header-loading rule to this field rather than folding it into the line above. */}
          <Skeleton variant="text" lines={1} className="w-24" />
          <CaptureStateBadge context="detail" loading />
        </header>
        <div className="flex flex-col gap-3">
          <Skeleton variant="block" className="h-14 w-full rounded-lg" />
          <Skeleton variant="block" className="h-14 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className={cx('flex flex-col gap-6', className)}>
      {/* Header, `DownloadAction` and its own error callout share `space-4` (§7 "Panel header to
       * `DownloadAction`"); the group as a whole keeps `space-6` from `ParticipantsTable` (§7
       * "`DownloadAction` to `ParticipantsTable`"). A single uniform gap on the outer container
       * cannot express two different steps, so the header-to-action run gets its own wrapper. */}
      <div className="flex flex-col gap-4">
        <header className="flex flex-col gap-3">
          <div>
            {/* `<h2>`, not `<h1>`: this panel is a section of a page that already carries its own
             * page-level heading (T076's route) — matching `Callout`'s own "keeps a sane outline"
             * reasoning for a component that is always nested. */}
            {/* §12.5: `MapThumbnail` at `lg` (96px) beside the map name — composed, never
             * re-implemented (T429). A `null` map keeps §11.2's `UnresolvedIdentifier` treatment
             * and no thumbnail, which `MapThumbnail`'s own `mapName == null` branch already
             * renders byte-identically to the previous bare `UnresolvedIdentifier` call. */}
            <h2 className="font-display text-xl font-semibold text-text-primary">
              <MapThumbnail thumbnailUrl={match.mapThumbnailUrl} mapName={match.map} size="lg" />
            </h2>
            <p className="mt-1 font-sans text-sm text-text-secondary">
              {match.leaderboardName}
              <span aria-hidden="true"> · </span>
              {match.durationLabel}
              {match.gameVersion != null && (
                <>
                  <span aria-hidden="true"> · </span>
                  {match.gameVersion}
                </>
              )}
              <span aria-hidden="true"> · </span>
              {match.playedAtLabel}
            </p>
          </div>
          <CaptureStateBadge
            context="detail"
            captureStatus={match.captureStatus}
            captureDeadlineAt={match.captureDeadlineAt}
          />
        </header>

        {match.captureStatus === 'stored' && (
          <Button
            variant="secondary"
            size="lg"
            loading={downloadState === 'loading'}
            loadingLabel="Preparing your download…"
            onClick={onDownload}
            className="self-start"
          >
            Download replay
          </Button>
        )}

        {downloadState === 'error' && (
          <Callout tone="danger" heading="The download link could not be created. Try again." />
        )}
      </div>

      <ParticipantsTable teams={match.teams} />
    </div>
  )
}

function ParticipantsTable({ teams }: { teams: TeamGroupData[] }) {
  return (
    <div className="flex flex-col gap-5">
      {teams.map((team) => (
        <TeamGroup key={team.id} team={team} />
      ))}
    </div>
  )
}

/** §12.3's `TeamResult` marker, per `TeamGroup` — computed here from `ParticipantData.result`
 * (`MatchOutcome`, this component's own three-state read), mapped to `MatchParticipantResult`
 * (`"unknown"` -> `null`) so the identical table `computeTeamResult` already implements in
 * `MatchRow` (§12.3) decides it here too — one answer to "did this side win", never re-derived
 * (§12.5's own "this panel composes the three marks; it never re-implements one" extended to this
 * marker, T431). */
function teamResultOf(participants: ParticipantData[]): TeamResultKind {
  return computeTeamResult(
    participants.map((participant) => ({
      result: participant.result === 'unknown' ? null : participant.result,
    })),
  )
}

function TeamGroup({ team }: { team: TeamGroupData }) {
  // §8 names three tiers: 375 one card per participant, 768 two participants side by side, 1280 a
  // real table. `xl` is the named breakpoint for the table (`lg` is 1024, reserved by §8 for
  // cards — see `useMediaQuery.ts`'s own DS-5 table); `md` (768) is the middle tier.
  const isTable = useBreakpoint('xl')
  const isTwoColumn = useBreakpoint('md')
  const headingId = `match-detail-team-${team.id}`
  const resultKind = teamResultOf(team.participants)

  return (
    <section aria-labelledby={headingId}>
      {/* §12.5: "Team 1 — Won" — the same marker `MatchRow`'s own group heading carries (§12.3),
       * joined here rather than a second, independently-worded signal. */}
      <h3
        id={headingId}
        className="mb-2 flex items-center gap-2 font-sans text-sm font-semibold text-text-secondary"
      >
        <span>{team.name}</span>
        {resultKind != null && (
          <>
            <span aria-hidden="true">—</span>
            <TeamResultMarker kind={resultKind} />
          </>
        )}
      </h3>
      {isTable ? (
        <table className="w-full border-collapse text-left font-sans text-sm">
          {/* The same words reach a screen reader (§9's existing caption rule, extended by §12.3):
           * nesting `TeamResultMarker`'s own `<span>` inside the caption is enough, since a
           * caption's accessible name is the concatenation of its descendants' text. */}
          <caption className="sr-only">
            {team.name}
            {resultKind != null && (
              <>
                {' '}
                — <TeamResultMarker kind={resultKind} />
              </>
            )}
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="py-3 pr-4 font-normal text-text-secondary">
                Player
              </th>
              <th scope="col" className="py-3 pr-4 font-normal text-text-secondary">
                Civilisation
              </th>
              <th scope="col" className="py-3 pr-4 font-normal text-text-secondary">
                Result
              </th>
              <th scope="col" className="py-3 text-right font-normal text-text-secondary">
                Rating
              </th>
            </tr>
          </thead>
          <tbody>
            {team.participants.map((participant) => (
              <tr key={participant.id} className="border-b border-border">
                {/* §12.5: the swatch lives inside the Player cell, not a colour column of its own
                 * (player-colour-swatch.md §2a) — composed, never re-implemented (T429). */}
                <th scope="row" className="py-3 pr-4 font-normal text-text-primary">
                  <span className="inline-flex items-center gap-2">
                    <PlayerColourSwatch
                      colorId={participant.colorId}
                      playerName={participant.alias}
                      size="sm"
                    />
                    <span>{participant.alias}</span>
                  </span>
                </th>
                <td className="py-3 pr-4">
                  <ParticipantCivilisation
                    civId={participant.civId}
                    civName={participant.civName}
                    civIconUrl={participant.civIconUrl}
                  />
                </td>
                <td className="py-3 pr-4">
                  <ResultLabel result={participant.result} />
                </td>
                <td className="py-3 text-right">
                  <RatingFigure
                    rating={participant.rating}
                    ratingChange={participant.ratingChange}
                    size="sm"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        // §8's 768 tier: two participants side by side within a `TeamGroup`, still cards (never
        // a table below `xl`). `gap-2` reused rather than a new column-gap value invented for a
        // register match-history.md §7 does not name.
        <ul className={isTwoColumn ? 'grid grid-cols-2 gap-2' : 'flex flex-col gap-2'}>
          {team.participants.map((participant) => (
            <li
              key={participant.id}
              className="flex flex-col gap-1 rounded-lg border border-border p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <PlayerColourSwatch
                    colorId={participant.colorId}
                    playerName={participant.alias}
                    size="sm"
                  />
                  <span className="font-sans text-sm font-semibold text-text-primary">
                    {participant.alias}
                  </span>
                </span>
                <ResultLabel result={participant.result} />
              </div>
              <div className="flex items-center justify-between gap-3 font-sans text-xs">
                <ParticipantCivilisation
                  civId={participant.civId}
                  civName={participant.civName}
                  civIconUrl={participant.civIconUrl}
                />
                <RatingFigure
                  rating={participant.rating}
                  ratingChange={participant.ratingChange}
                  size="sm"
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
