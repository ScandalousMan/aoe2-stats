import type { ReactNode } from 'react'
import { useId } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §13 (T548, FR-024).
// `ErrorState` is not `Callout`: a `Callout` sits beside content that is still there, `ErrorState`
// replaces content that is gone — a route whose request failed renders this, a route whose
// secondary action failed renders a `Callout` above content that still renders (§1 of the same
// file). The stripe-and-heading grammar is deliberately `Callout`'s: a reader who has learned one
// failure grammar in this product should not have to learn a second.

// The recovery action is mandatory (FR-024: "a failure must not leave the control that caused it
// permanently unusable"). There is no third case beyond an action or an explicit `recovery="none"`
// with a sentence, and that is enforced here at the type level rather than left to a runtime guard
// that could silently pass an `ErrorState` with neither.
type ErrorStateRecovery =
  | {
      /** The recovery: a `Button`, `secondary` variant — retry, go back, or a contact route. */
      action: ReactNode
      recovery?: undefined
      recoveryText?: undefined
    }
  | {
      action?: undefined
      /** The explicit refusal: there is nothing to retry. `recoveryText` is required alongside it
       * — the absence of an action must never be silent. */
      recovery: 'none'
      /** What the reader can do instead ("this match's replay is past Microsoft's retention
       * window; nothing can retrieve it"). */
      recoveryText: ReactNode
    }

export type ErrorStateProps = {
  /** What failed, in the reader's terms — never a raw stack trace, a JSON body or an HTTP status. */
  heading: ReactNode
  /** What it means for them, and what happens next. Always rendered in `text-primary`, never in
   * the danger ink — the tone colours the stripe and the heading only, the same rule `Callout`
   * carries and for the same reason. */
  explanation: ReactNode
  /** An error code or reference, in `type-machine`, for a support message. Selectable text, never
   * an image or a tooltip. */
  technicalDetail?: ReactNode
  /** Heading level for the `Section` or `Panel` body this renders inside. Defaults to 2, matching
   * `Callout`'s own default. */
  headingLevel?: 2 | 3 | 4
  /** `true` when this replaces content after an interaction (a retry that failed again), so the
   * region is announced (`role="alert"`). `false` (the default) for the initial render of a failed
   * route: an alert on first paint double-announces, `Callout`'s own rule for the same reason. */
  announce?: boolean
  className?: string
} & ErrorStateRecovery

/** An `ErrorState` with no heading renders nothing — a failure with no words is worse than a blank
 * region, because the region at least does not claim to be an explanation. This is a caller
 * defect, not a normal state, and the empty story exists to show it rather than to recommend it. */
export function ErrorState({
  heading,
  explanation,
  action,
  recovery,
  recoveryText,
  technicalDetail,
  headingLevel = 2,
  announce = false,
  className,
}: ErrorStateProps) {
  const headingId = useId()
  if (!heading) return null

  const Heading = `h${headingLevel}` as const as 'h2' | 'h3' | 'h4'

  return (
    <div
      role={announce ? 'alert' : undefined}
      aria-labelledby={headingId}
      className={cx('border-l-2 border-danger py-6 pl-4', className)}
    >
      <Heading id={headingId} className="type-display text-xl font-semibold text-danger">
        {heading}
      </Heading>
      <p className="type-body text-md mt-2 max-w-measure text-text-primary">{explanation}</p>
      {recovery === 'none' ? (
        <p className="type-body text-md mt-4 max-w-measure text-text-primary">{recoveryText}</p>
      ) : (
        <div className="mt-4 flex flex-col gap-3 md:flex-row">{action}</div>
      )}
      {technicalDetail && (
        <p className="type-machine mt-4 break-words text-sm text-text-secondary">
          {technicalDetail}
        </p>
      )}
    </div>
  )
}
