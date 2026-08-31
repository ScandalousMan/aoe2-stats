import { type ReactNode, useState } from 'react'
import { iconTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'

// packages/design-system/specs/civilisation-icon.md

export type CivilisationIconSize = 'md' | 'lg'

export interface CivilisationIconProps {
  /** `packages/game-assets`' `civilisationIcon(civName)` result, resolved by the caller —
   * `undefined` when the pack does not cover this civilisation (FR-010's designed degrade path,
   * not a defect; §4 "empty"). This component never imports the pack and never builds this URL
   * itself. */
  iconUrl?: string
  /** The civilisation's name, resolved upstream by feature 002's `civ_id -> name` mapping — always
   * present alongside a real `civ_id` per `contracts/http-api.md`. Absent or blank is a contract
   * violation this component still renders safely: "Unknown civilisation", with no mark (§4). */
  name?: ReactNode
  /** `md` in `MatchRow`, `lg` in `MatchDetailPanel`'s participants (game-asset-tokens.md's
   * per-component mapping). */
  size?: CivilisationIconSize
  className?: string
}

const SIZE_TOKEN: Record<CivilisationIconSize, string> = {
  md: iconTokens.md,
  lg: iconTokens.lg,
}

function hasName(name: ReactNode): boolean {
  if (name == null) return false
  if (typeof name === 'string') return name.trim() !== ''
  return true
}

/** Mark and name as one unit (§2) — never the mark alone (design-system rule 4). The mark is
 * removed from the DOM, never merely hidden, on a failed decode so the error render is
 * byte-identical to the `iconUrl === undefined` render (§4 "error"). */
export function CivilisationIcon({ iconUrl, name, size = 'md', className }: CivilisationIconProps) {
  // Tracks the *url* that failed, not a boolean — a later render with a different `iconUrl` (a
  // new civilisation) must not stay stuck showing the previous one's failure.
  const [failedUrl, setFailedUrl] = useState<string | undefined>(undefined)
  const dimension = SIZE_TOKEN[size]

  if (!hasName(name)) {
    return <span className={className}>Unknown civilisation</span>
  }

  const showMark = iconUrl != null && iconUrl !== failedUrl

  return (
    <span className={cx('inline-flex items-center gap-2', className)}>
      {showMark && (
        <img
          src={iconUrl}
          alt=""
          loading="lazy"
          decoding="async"
          style={{ width: dimension, height: dimension }}
          className="rounded-sm"
          onError={() => setFailedUrl(iconUrl)}
        />
      )}
      <span>{name}</span>
    </span>
  )
}
