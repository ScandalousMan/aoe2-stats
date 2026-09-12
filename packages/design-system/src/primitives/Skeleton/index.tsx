import { cx } from '../../lib/cx'
import { useDelayedVisible } from '../../lib/useDelayedVisible'

// packages/design-system/specs/shared-primitives.md#Skeleton

export type SkeletonVariant = 'text' | 'number' | 'block'

export interface SkeletonProps {
  variant?: SkeletonVariant
  /** `text` only: number of lines. Widths vary 60–90% per line so a stack of lines does not read
   * as a single grey rectangle. */
  lines?: number
  /** Sizes the footprint with token-backed Tailwind width utilities (`w-16`, …), supplied by the
   * caller so the skeleton matches the content it stands in for. On `block`/`number` this also
   * takes a height utility (`h-10`, …): the whole element is the footprint. On `text` it does not:
   * each line's height is the fixed `h-4` below, set by line count rather than by the caller, so a
   * height utility here would size the wrapper without changing what any line renders — pass width
   * only for `text`. */
  className?: string
}

// T528: closes an arbitrary animation value. The continuous pulse now reads the real
// `animate-pulse` utility (`motion.json`'s `animation.spin`/`pulse` group, T516/T512) instead of
// an arbitrary bracket composing the duration and easing variables by hand, and still stops on its
// resting frame under `prefers-reduced-motion` via `motion-safe:`.
const pulse = 'rounded-control bg-surface-sunken motion-safe:animate-pulse'

const textLineWidths = ['w-full', 'w-11/12', 'w-4/5', 'w-3/4', 'w-5/6']

/** Loading is the only state a `Skeleton` has. It renders nothing for the first `duration.normal`
 * (200ms) so a load that resolves quickly never flashes a pulse, and the blocks themselves carry
 * `aria-hidden`: the surrounding region (not this component) owns `aria-busy` and announces once,
 * not once per block. A skeleton with a zero line/count count renders nothing. */
export function Skeleton({ variant = 'block', lines = 1, className }: SkeletonProps) {
  const visible = useDelayedVisible()
  if (!visible || lines <= 0) return null

  if (variant === 'text') {
    // The caller's className sizes the stack's footprint (a width), not each line, applied here on
    // the wrapper rather than per line. Every `lines={n}` call site in this package today passes
    // `n === 1` when it passes a className at all (`SignInScreen`'s three-line skeleton passes
    // none), so no shipped caller distinguishes the two placements — with one line, sizing the
    // wrapper or the line is the same rectangle. The reason for choosing the wrapper is structural,
    // not evidenced by a call site: `textLineWidths` are Tailwind fraction utilities
    // (`w-11/12`, …), which resolve as a percentage of the nearest sized ancestor — putting the
    // caller's fixed width on the wrapper is what makes that percentage the caller's footprint
    // rather than the line's own, unrelated box. Moving className onto each line would make its
    // fixed width win outright on every line, collapsing the 60–90% variance the `lines` doc
    // comment above describes. If a multi-line, class-sized caller is ever added, this is the
    // question that decides the placement, not a preference: whether `textLineWidths`' entries stay
    // fractional (wrapper) or become their own fixed widths (per line, and the variance would need
    // to be re-derived some other way).
    return (
      <div aria-hidden="true" className={cx('flex flex-col gap-2', className)}>
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
