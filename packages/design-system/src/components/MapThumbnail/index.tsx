import { useState } from 'react'
import { iconTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'

// packages/design-system/specs/map-thumbnail.md

export type MapThumbnailSize = 'sm' | 'md' | 'lg'

export interface MapThumbnailProps {
  /** `packages/game-assets`' `mapThumbnail(mapName)` result, resolved by the caller — `undefined`
   * for any map the pack does not cover (an unbounded identifier space: custom and tournament
   * maps, §2/§4). This component never imports the pack and never builds this URL itself. */
  thumbnailUrl?: string
  /** `matches.map_name` verbatim. `null` means the source recorded no map name at all — a
   * different, rarer fact than "the pack does not cover this name" — and renders the
   * `UnresolvedIdentifier` treatment instead of a blank gap (§4 "empty"). */
  mapName?: string | null
  /** `sm` (32px) in `MatchRow`'s 1280 table row, `md` (64px, default) in a card/list, `lg` (96px)
   * in `MatchDetailPanel`'s header (§3). */
  size?: MapThumbnailSize
  className?: string
}

const SIZE_TOKEN: Record<MapThumbnailSize, string> = {
  sm: iconTokens.lg,
  md: iconTokens['2xl'],
  lg: iconTokens['3xl'],
}

const GAP_CLASS: Record<MapThumbnailSize, string> = {
  sm: 'gap-2',
  md: 'gap-3',
  lg: 'gap-3',
}

/** §11.2's treatment for an identifier this service never recorded at all — reproduced here rather
 * than imported from `MatchDetailPanel` (which will itself come to consume `MapThumbnail` in
 * T431; importing the other way would be a circular dependency between the two). */
function UnresolvedMapName() {
  return <span className="font-mono text-sm text-text-secondary">Map — unresolved</span>
}

/** Frame and thumbnail and name as one unit (§2) — never the thumbnail alone (design-system rule
 * 4). The frame is drawn only when an image is actually rendered inside it (§2), and is removed
 * together with the image, never left as an empty box, on a failed decode (§4 "error"). */
export function MapThumbnail({ thumbnailUrl, mapName, size = 'md', className }: MapThumbnailProps) {
  // Tracks the *url* that failed, not a boolean — a later render with a different `thumbnailUrl`
  // (a new map) must not stay stuck showing the previous one's failure.
  const [failedUrl, setFailedUrl] = useState<string | undefined>(undefined)
  const dimension = SIZE_TOKEN[size]

  if (mapName == null) {
    return (
      <span className={cx('inline-flex items-center', GAP_CLASS[size], className)}>
        <UnresolvedMapName />
      </span>
    )
  }

  const showThumbnail = thumbnailUrl != null && thumbnailUrl !== failedUrl

  return (
    <span className={cx('inline-flex items-center', GAP_CLASS[size], className)}>
      {showThumbnail && (
        <span
          className="flex items-center justify-center rounded-md border border-border"
          style={{ width: dimension, height: dimension }}
        >
          <img
            src={thumbnailUrl}
            alt=""
            loading="lazy"
            decoding="async"
            style={{ width: dimension, height: dimension, objectFit: 'contain' }}
            onError={() => setFailedUrl(thumbnailUrl)}
          />
        </span>
      )}
      <span>{mapName}</span>
    </span>
  )
}
