import { useId } from 'react'
import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import type { ButtonSize } from '../Button'
import { Button } from '../Button'

// packages/design-system/specs/favourite-toggle.md

export interface FavouriteToggleProps {
  /** Whether this profile is in the caller's own favourites. Meaningless while `authenticated` is
   * `false` — FR-015 forbids disclosing a favourited state to a signed-out visitor, so this prop
   * is simply not read in that case (§4, §5a). */
  favourited: boolean
  /** Whether a session exists. Drives the signed-out state (§5a) — this is `false`, never
   * `favourited: false`, for a visitor with no session (§4). */
  authenticated: boolean
  /** The caller's favourites are at the configured bound (FR-016). Only affects the unmarked→add
   * direction (§4) — a `favourited` profile is never blocked by the bound. */
  atLimit?: boolean
  /** The configured maximum, shown as a plain number in the bounded explanation (§5). Required
   * whenever `atLimit` is `true` and `favourited` is `false`. */
  max?: number
  /** A `PUT` or `DELETE` is in flight. The direction is read from `favourited` (§5's "flip only
   * on the 200"): `favourited: false` while `loading` means a `PUT` is in flight, `favourited:
   * true` while `loading` means a `DELETE` is in flight. */
  loading?: boolean
  /** Issues `PUT /api/favourites/{profile_id}` (§5). Never called while signed out. */
  onAdd?: () => void
  /** Issues `DELETE /api/favourites/{profile_id}` (§5). Never called while signed out. */
  onRemove?: () => void
  /** The real sign-in destination, carrying this profile's own location as its return place
   * (§5a) — this component never invents the path, the same discipline `PlayerResultRow.href`
   * and `MatchRowData.href` already carry. Required whenever `authenticated` is `false`. */
  signInHref?: string
  /** Wires the sign-in navigation into the caller's own router (T388's pattern) instead of
   * forcing a full document reload — the identical seam `PlayerResultRow.onNavigate` and
   * `MatchRow.onNavigate` already offer. */
  onNavigate?: (href: string) => void
  size?: ButtonSize
  className?: string
}

// §2: "an original geometric bookmark/pin device — no star, crest, unit, portrait or lettering
// from the game". Purely decorative (aria-hidden) and never the sole carrier of state — the label
// text always carries it too (§5, §9). Sized from the adjacent font-size (1em, gap DS-7), never a
// fixed pixel size, and swaps outline/filled with a token motion transition (§6).
function StateGlyph({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="h-[1em] w-[1em] shrink-0 transition-[fill,opacity] duration-120 ease-standard motion-reduce:duration-0"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    >
      <path d="M3.5 1.5h9a.5.5 0 0 1 .5.5v12.2a.4.4 0 0 1-.63.33L8 11.2l-4.37 3.33a.4.4 0 0 1-.63-.33V2a.5.5 0 0 1 .5-.5Z" />
    </svg>
  )
}

/** Lets a signed-in user mark or unmark a third-party profile as a favourite in one gesture
 * (FR-013), and asks a signed-out visitor to sign in without losing their place (US5 scenario 5).
 * Never rendered on `subject="self"` (`profile-summary.md` §11.1 point 3) — that is the
 * consumer's decision, not this component's: it always renders whatever state it is given. See
 * `packages/design-system/specs/favourite-toggle.md`. */
export function FavouriteToggle({
  favourited,
  authenticated,
  atLimit = false,
  max,
  loading = false,
  onAdd,
  onRemove,
  signInHref,
  onNavigate,
  size = 'md',
  className,
}: FavouriteToggleProps) {
  const explanationId = useId()

  if (!authenticated) {
    return (
      <SignedOutControl
        signInHref={signInHref}
        onNavigate={onNavigate}
        size={size}
        className={className}
      />
    )
  }

  // §5: removal is always permitted, so a favourited profile at the bound still renders the
  // marked default below, never the bounded/disabled state.
  const bounded = atLimit && !favourited
  const loadingLabel = favourited ? 'Removing…' : 'Adding…'
  const label = favourited ? 'Remove from favourites' : 'Add to favourites'

  const button = (
    <Button
      type="button"
      variant="ghost"
      size={size}
      aria-pressed={favourited}
      disabled={bounded}
      loading={loading}
      loadingLabel={loadingLabel}
      leadingIcon={<StateGlyph filled={favourited} />}
      aria-describedby={bounded ? explanationId : undefined}
      onClick={favourited ? onRemove : onAdd}
      // Only wrapped in a layout `<div>` for the bounded case below (§2's "Explanation, present
      // only in the bounded and disabled cases"), so `className` lands on the button itself in
      // every other state — the same seam `PlayerResultRow` and `MatchRow` give their own root
      // element, and what lets a consumer size or align this control without reaching past it.
      className={bounded ? undefined : className}
    >
      {label}
    </Button>
  )

  if (!bounded) return button

  return (
    <div className={cx('flex flex-col items-start gap-1', className)}>
      {button}
      <span id={explanationId} className="font-sans text-sm text-text-secondary">
        You've reached your favourites limit of {max}. Remove one to add another.
      </span>
    </div>
  )
}

// §5a: discoverable but unable to assert a favourited state it cannot know. A real activation —
// never a silent no-op — that carries the caller back to exactly where they were (US5 scenario 5).
function SignedOutControl({
  signInHref,
  onNavigate,
  size,
  className,
}: {
  signInHref?: string
  onNavigate?: (href: string) => void
  size: ButtonSize
  className?: string
}) {
  const href = signInHref ?? '#'
  return (
    <Button
      href={href}
      variant="ghost"
      size={size}
      leadingIcon={<StateGlyph filled={false} />}
      onClick={createRowLinkClickHandler(href, onNavigate)}
      className={className}
    >
      Sign in to add favourites
    </Button>
  )
}
