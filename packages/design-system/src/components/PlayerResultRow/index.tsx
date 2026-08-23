import { cx } from '../../lib/cx'

// packages/design-system/specs/player-search.md

export interface PlayerSearchResultData {
  /** Used only as the React list key — never rendered (§4, no numeric identifier surfaces here). */
  profileId: string
  /** The profile route (T322's `players.$profileId.tsx`). `PlayerResultRow` never invents this
   * path, mirroring `MatchRowData.href`'s identical rule (match-history.md). */
  href: string
  alias: string
  /** Bracketed beside the alias when present — the row's fallback distinguishing signal on a
   * locally-known result that carries neither country nor a games-played count (§4). */
  clan?: string | null
  /** Present on essentially every result from either search path — the closest thing to a
   * guarantee `PlayerResultRow` has (§4). */
  country?: string | null
  /** `null` for a result answered by FR-004d's local fallback: `aoe_profiles` has no
   * games-played column, so `Standing` renders nothing for it — never a fabricated `0` (§4). */
  gamesPlayed: number | null
}

export interface PlayerResultRowProps {
  result: PlayerSearchResultData
  className?: string
}

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring'

/** One search result. The whole row is a single link (§2, §9) — everything inside, including
 * `Standing`, is non-interactive text with no hover of its own; the row itself owns the hover fill,
 * the same rule `MatchRow` states for `MatchRow` (match-history.md). Stacks into a full-width card
 * below `md`; from `md` up it becomes a plain divided row with country and standing moved onto the
 * alias's own line (§8). Neither field ever truncates — a half-visible alias is exactly the
 * near-identical-names failure FR-002 exists to prevent. */
export function PlayerResultRow({ result, className }: PlayerResultRowProps) {
  return (
    <a
      href={result.href}
      className={cx(
        'flex flex-col gap-1 rounded-lg border border-border bg-surface p-4',
        'md:flex-row md:items-center md:justify-between md:gap-4 md:rounded-none',
        'md:border-x-0 md:border-t-0 md:border-b md:bg-transparent md:px-0 md:py-3',
        'transition-colors duration-120 ease-standard hover:bg-surface-sunken',
        focusRing,
        className,
      )}
    >
      <span className="flex flex-wrap items-baseline gap-2">
        <span className="font-sans text-sm font-semibold text-text-primary">{result.alias}</span>
        {result.clan && (
          <span className="font-sans text-xs text-text-secondary">[{result.clan}]</span>
        )}
      </span>
      <span className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        {result.country && (
          <span className="font-sans text-xs text-text-secondary">{result.country}</span>
        )}
        {result.gamesPlayed != null && (
          <span className="font-mono text-xs text-text-primary">{result.gamesPlayed} games</span>
        )}
      </span>
    </a>
  )
}
