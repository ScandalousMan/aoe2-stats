import { cx } from '../../lib/cx'
import { useDelayedVisible } from '../../lib/useDelayedVisible'

// packages/design-system/specs/shared-primitives.md#Skeleton

export type SkeletonVariant = 'text' | 'number' | 'block'

export interface SkeletonProps {
  variant?: SkeletonVariant
  /** `text` only: number of lines. Widths vary 60–90% per line so a stack of lines does not read
   * as a single grey rectangle. */
  lines?: number
  /** Sizes the footprint with token-backed Tailwind width/height utilities (`w-16`, `h-10`, …),
   * supplied by the caller so the skeleton matches the content it stands in for. */
  className?: string
}

// Continuous pulse has no motion token of its own (closest named duration is `duration.slow`), so
// the keyframe reads the token's CSS variable directly instead of a literal — the same technique
// the generated tokens themselves use — and stops on its resting frame under
// `prefers-reduced-motion` via `motion-safe:`.
const pulse =
  'rounded-sm bg-surface-sunken motion-safe:animate-[pulse_var(--ds-motion-duration-slow)_var(--ds-motion-easing-standard)_infinite]'

const textLineWidths = ['w-full', 'w-11/12', 'w-4/5', 'w-3/4', 'w-5/6']

/** Loading is the only state a `Skeleton` has. It renders nothing for the first `duration.normal`
 * (200ms) so a load that resolves quickly never flashes a pulse, and the blocks themselves carry
 * `aria-hidden`: the surrounding region (not this component) owns `aria-busy` and announces once,
 * not once per block. A skeleton with a zero line/count count renders nothing. */
export function Skeleton({ variant = 'block', lines = 1, className }: SkeletonProps) {
  const visible = useDelayedVisible()
  if (!visible || lines <= 0) return null

  if (variant === 'text') {
    return (
      <div aria-hidden="true" className="flex flex-col gap-2">
        {Array.from({ length: lines }, (_, index) => (
          <div
            key={index}
            className={cx(pulse, 'h-4', textLineWidths[index % textLineWidths.length])}
          />
        ))}
      </div>
    )
  }

  return <div aria-hidden="true" className={cx(pulse, className)} />
}
