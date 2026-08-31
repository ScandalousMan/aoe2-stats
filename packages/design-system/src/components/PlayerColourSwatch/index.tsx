import type { ReactNode } from 'react'
import { iconTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'

// packages/design-system/specs/player-colour-swatch.md
// Asset origin: none — a player colour is eight token values, not a bitmap (spec, "Asset origin").

export type PlayerColourSwatchSize = 'xs' | 'sm'

export interface PlayerColourSwatchProps {
  /** `match_players.color_id` after read-time enrichment (data-model.md §6). `1`..`8` render the
   * game's canonical colour; anything else — `null` (companion never heard of this match, a
   * legitimate resting state) or an out-of-range value neither the game nor this service defines
   * — renders **identically**, a neutral chip (§4 "empty" and "error"). */
  colorId?: number | null
  /** The player's name, already rendered by the caller beside this chip (§2a) — this component
   * never repeats it. Required, and blank/absent renders nothing at all: a chip must never exist
   * with no name to sit beside. */
  playerName: ReactNode
  /** `xs` (12px, default) in `MatchRow`; `sm` (16px) in `MatchDetailPanel`'s participants table
   * (§3). */
  size?: PlayerColourSwatchSize
  className?: string
}

const COLOUR_BY_ID: Record<number, { fill: string; label: string }> = {
  1: { fill: 'bg-player-1', label: 'Blue' },
  2: { fill: 'bg-player-2', label: 'Red' },
  3: { fill: 'bg-player-3', label: 'Green' },
  4: { fill: 'bg-player-4', label: 'Yellow' },
  5: { fill: 'bg-player-5', label: 'Teal' },
  6: { fill: 'bg-player-6', label: 'Purple' },
  7: { fill: 'bg-player-7', label: 'Grey' },
  8: { fill: 'bg-player-8', label: 'Orange' },
}

const SIZE_TOKEN: Record<PlayerColourSwatchSize, string> = {
  xs: iconTokens.xs,
  sm: iconTokens.sm,
}

function hasName(playerName: ReactNode): boolean {
  if (playerName == null) return false
  if (typeof playerName === 'string') return playerName.trim() !== ''
  return true
}

/** Chip and hidden colour name as one unit (§2). Renders `null` — nothing at all — when
 * `playerName` is blank, so a colour never appears with no owner beside it (§2a). An out-of-range
 * `colorId` and a `null` one render byte-identically: a neutral `surface-sunken` fill inside the
 * same frame, never an error tone (§4). No hex string anywhere in this file — the fill and its
 * frame come from tokens only (`player-1`…`player-8`, `surface-sunken`, `border-strong`). */
export function PlayerColourSwatch({
  colorId,
  playerName,
  size = 'xs',
  className,
}: PlayerColourSwatchProps) {
  if (!hasName(playerName)) return null

  const known = colorId != null ? COLOUR_BY_ID[colorId] : undefined
  const dimension = SIZE_TOKEN[size]

  return (
    <span className={cx('inline-flex items-center', className)}>
      <span
        aria-hidden="true"
        className={cx(
          'rounded-sm border border-border-strong',
          known ? known.fill : 'bg-surface-sunken',
        )}
        style={{ width: dimension, height: dimension }}
      />
      <span className="sr-only">{known ? `Colour: ${known.label}` : 'Colour: not recorded'}</span>
    </span>
  )
}
