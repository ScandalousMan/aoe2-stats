import { useState } from 'react'
import { iconTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'

// packages/design-system/specs/player-avatar.md

export type PlayerAvatarSize = 'sm' | 'md'

export interface PlayerAvatarProps {
  /** The profile's Steam avatar hash, as the companion provider serves it — a hash, never a URL
   * (`contracts/http-api.md`). Absent, `null` or blank is a legitimate resting state, not an error
   * (§4 "empty"): a profile never seen in a companion response has no hash and never will. */
  avatarHash?: string | null
  /** `sm` (32px) in `ProfileSummary`'s `compact` variant. `md` (64px, default) in the `board`
   * identity bar (§3). */
  size?: PlayerAvatarSize
  className?: string
}

const SIZE_TOKEN: Record<PlayerAvatarSize, string> = {
  sm: iconTokens.lg,
  md: iconTokens['2xl'],
}

// The `width`/`height` attributes reserve intrinsic space before decode alongside the token-driven
// CSS size above (§8) — the pixel figures the tokens resolve to today (icon-lg 32px, icon-2xl
// 64px), not a second source of truth for the box's *displayed* size, which the CSS token controls.
const SIZE_PIXELS: Record<PlayerAvatarSize, number> = {
  sm: 32,
  md: 64,
}

// The one occurrence of Steam's avatar CDN host in this repository's front end (§2b). No `src`,
// `baseUrl` or `href` override prop exists on this component, and none may be added — an override
// would make this check meaningless.
const STEAM_AVATAR_CDN = 'https://avatars.steamstatic.com'

function hasHash(avatarHash?: string | null): avatarHash is string {
  return avatarHash != null && avatarHash.trim() !== ''
}

/** Builds the CDN URL from the hash — the one place in the system that does (§2b). The hash is an
 * unverified third-party string (constitution IX) and is URL-encoded before interpolation so a
 * value the provider never sanitised cannot change the shape of the URL. */
function buildAvatarUrl(hash: string): string {
  return `${STEAM_AVATAR_CDN}/${encodeURIComponent(hash)}_full.jpg`
}

/** Frame and fill first, image painted over it (§2). The frame is drawn in **every** state —
 * loaded, loading, error and empty alike — so the `border-strong`/`surface-sunken` box is the only
 * thing that ever changes position, never its footprint. `onError` removes the `<img>`, leaving the
 * frame and its fill: byte-identical to the no-hash render (§4 "error"). This component renders no
 * name of its own — the heading beside it always carries one (§2a) — and exposes no `src`,
 * `baseUrl` or `href` prop (§2b). */
export function PlayerAvatar({ avatarHash, size = 'md', className }: PlayerAvatarProps) {
  // Tracks the *hash* that failed, not a boolean — a later render with a different `avatarHash` (a
  // different profile) must not stay stuck showing the previous one's failure.
  const [failedHash, setFailedHash] = useState<string | undefined>(undefined)
  const dimension = SIZE_TOKEN[size]
  const pixels = SIZE_PIXELS[size]

  const showImage = hasHash(avatarHash) && avatarHash !== failedHash

  return (
    <span
      aria-hidden="true"
      className={cx(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-control border border-border-strong bg-surface-sunken',
        className,
      )}
      style={{ width: dimension, height: dimension }}
    >
      {showImage && (
        <img
          src={buildAvatarUrl(avatarHash as string)}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          width={pixels}
          height={pixels}
          style={{ width: dimension, height: dimension, objectFit: 'cover' }}
          onError={() => setFailedHash(avatarHash as string)}
        />
      )}
    </span>
  )
}
