import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §12 (T548, FR-023).
// `EmptyState` is not `Skeleton`: a `Skeleton` says "arriving", `EmptyState` says "settled, and
// there is nothing" — the two must never be ambiguous in a still image, so `EmptyState` always
// carries a sentence and never renders while a request is still in flight (§1 of the same file).
// It also does not answer "the request failed" — that is `ErrorState` (§13) — because "nothing
// here" and "we could not find out" are different facts a reader acts on differently.

export interface EmptyStateProps {
  /** What is not here, in six words or fewer. Required together with `explanation`: an
   * `EmptyState` with neither renders nothing at all — the guard against the blank-region defect
   * FR-023 names, the same shape `Callout`'s own empty guard already uses. */
  heading: ReactNode
  /** Why, in one or two sentences, in the reader's terms. */
  explanation: ReactNode
  /** The one thing that would fill the region — a secondary `Button` or a `Link`. Never disabled:
   * an empty state with nothing actionable simply omits this prop. */
  action?: ReactNode
  /** Heading level for the `Section` or `Panel` body this renders inside, so the document outline
   * stays correct. Defaults to 2, matching `Callout`'s own default. */
  headingLevel?: 2 | 3 | 4
  className?: string
}

/** An `EmptyState` with no heading and no explanation renders nothing at all — there is no such
 * thing as an empty empty state, and a wordless one is exactly the blank region FR-023 forbids. */
export function EmptyState({
  heading,
  explanation,
  action,
  headingLevel = 2,
  className,
}: EmptyStateProps) {
  if (!heading && !explanation) return null

  const Heading = `h${headingLevel}` as const as 'h2' | 'h3' | 'h4'

  return (
    <div className={cx('py-8', className)}>
      <Heading className="type-display text-xl font-semibold text-text-primary">{heading}</Heading>
      <p className="type-body text-md mt-2 max-w-measure text-text-secondary">{explanation}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
