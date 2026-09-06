import { useState } from 'react'
import { iconTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'
import { Tooltip } from '../Tooltip'

// packages/design-system/specs/country-flag.md — read §11 before touching this file: it
// supersedes the always-visible name and the "never a tab stop" rule below.

export type CountryFlagSize = 'sm' | 'md'

export interface CountryFlagProps {
  /** `packages/game-assets`' `countryFlag(code)` result, resolved by the caller — `undefined` for
   * a code outside the 249-file pack, or a value that is not a code at all. This component never
   * imports the pack and never builds this URL itself (§2a). */
  flagUrl?: string
  /** The country's name, already resolved upstream by `apps/web/src/features/players/format.ts`
   * (`Intl.DisplayNames`) from the API's ISO alpha-2 code — this component ships no country table
   * and never parses a code (§2a). Absent or blank renders nothing at all: a profile without a
   * country looks like a profile that never had one (§4 "empty", third case). */
  countryName?: string | null
  /** `sm` (16px, default) inline beside an alias — `ProfileSummary`'s `compact` variant. `md`
   * (24px) in the `board` identity bar (§3). */
  size?: CountryFlagSize
  className?: string
}

const SIZE_TOKEN: Record<CountryFlagSize, string> = {
  sm: iconTokens.sm,
  md: iconTokens.md,
}

function hasCountryName(countryName?: string | null): countryName is string {
  return countryName != null && countryName.trim() !== ''
}

/** Never the flag alone with no route to its name (design-system rule 4, and §2's rule 1: several
 * flags are indistinguishable at `icon-sm` without the word). §11 changes *where* the name lives
 * once a flag actually renders: it moves into a `Tooltip` on the flag (relation="label", a real
 * 44px `<button>` trigger) instead of sitting beside it as text. The frame is drawn only when an
 * image is actually rendered inside it, and is removed together with the image, never left as an
 * empty box, on a failed decode (§4 "error" — byte-identical to `flagUrl === undefined`). In both
 * of those absent-asset cases (§11.4) the name renders alone as plain, selectable text — no frame,
 * no button, no tab stop, no tooltip: nothing hangs a tooltip on a flag that is not there. Renders
 * `null` — nothing at all — when `countryName` is blank: the component refuses to render half of a
 * pair (§4 "empty", third case). */
export function CountryFlag({ flagUrl, countryName, size = 'sm', className }: CountryFlagProps) {
  // Tracks the *url* that failed, not a boolean — a later render with a different `flagUrl` (a
  // new country) must not stay stuck showing the previous one's failure.
  const [failedUrl, setFailedUrl] = useState<string | undefined>(undefined)

  if (!hasCountryName(countryName)) return null

  const height = SIZE_TOKEN[size]
  // The token sets the box's height; the width follows at 4:3 — the flag-icons pack's aspect,
  // never squeezed into a square (§3).
  const width = `calc(${height} * 4 / 3)`
  const showFlag = flagUrl != null && flagUrl !== failedUrl

  if (!showFlag) {
    // §11.4 — the two absent-asset cases: the country name alone, as plain, selectable text, with
    // no frame, no button, no tab stop and no tooltip. Byte-identical between "pack does not cover
    // it" and "the image failed to load/decode".
    return <span className={cx('font-sans font-normal', className)}>{countryName}</span>
  }

  return (
    // §11.2: the trigger is the framed flag itself; the tooltip's content is the qualified,
    // already-resolved country name. `relation="label"` (the default) is correct here and only
    // here in this file — the trigger's only visible content is the image, so the tooltip *is*
    // its accessible name (tooltip.md §3).
    <Tooltip content={countryName} qualifier="Country:" className={className}>
      <span
        className="flex items-center justify-center overflow-hidden rounded-control border border-border"
        style={{ height, width }}
      >
        <img
          src={flagUrl}
          alt=""
          loading="lazy"
          decoding="async"
          style={{ height, width, objectFit: 'contain' }}
          onError={() => setFailedUrl(flagUrl)}
        />
      </span>
    </Tooltip>
  )
}
