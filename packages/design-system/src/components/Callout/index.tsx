import type { ReactNode } from 'react'
import { useId } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/shared-primitives.md#Callout

export type CalloutTone = 'info' | 'success' | 'warning' | 'danger'

export interface CalloutProps {
  tone: CalloutTone
  heading: ReactNode
  /** Document heading level for this callout's heading, so the surrounding screen keeps a sane
   * outline (sign-in-screen.md uses `<h2>`; a callout nested under a screen's own `<h2>`/`<h3>`
   * hierarchy uses a deeper one). Defaults to 2. */
  headingLevel?: 2 | 3 | 4
  children?: ReactNode
  /** Action row — usually one or two `Button`s. */
  actions?: ReactNode
  /** Focus is moved here (tabIndex=-1) by the consumer on mount, per sign-in-screen.md §8. */
  headingRef?: React.Ref<HTMLHeadingElement>
  className?: string
}

// Tone colours only the stripe and the heading — never the body (README, "the rule that answers
// light `warning`"). Collapsing that into a per-component judgement call is exactly the bug this
// rule exists to rule out.
const toneClasses: Record<CalloutTone, { stripe: string; heading: string }> = {
  info: { stripe: 'border-info', heading: 'text-info' },
  success: { stripe: 'border-success', heading: 'text-success' },
  warning: { stripe: 'border-warning', heading: 'text-warning' },
  danger: { stripe: 'border-danger', heading: 'text-danger' },
}

const roleForTone: Record<CalloutTone, 'status' | 'alert'> = {
  info: 'status',
  success: 'status',
  warning: 'status',
  danger: 'alert',
}

/** A callout with neither heading nor body renders nothing at all — not an empty bordered box.
 * This is the empty state that ships by accident (shared-primitives.md, §Callout, §empty). */
export function Callout({
  tone,
  heading,
  headingLevel = 2,
  children,
  actions,
  headingRef,
  className,
}: CalloutProps) {
  const headingId = useId()
  if (!heading && !children) return null

  const { stripe, heading: headingColor } = toneClasses[tone]
  const Heading = `h${headingLevel}` as const as 'h2' | 'h3' | 'h4'

  return (
    <div
      role={roleForTone[tone]}
      aria-labelledby={headingId}
      className={cx('rounded-panel border-l-2 bg-surface-raised p-4 md:p-5', stripe, className)}
    >
      <Heading
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className={cx('font-sans text-md font-semibold', headingColor)}
      >
        {heading}
      </Heading>
      {children && (
        <div className="mt-2 space-y-3 font-sans text-sm text-text-primary">{children}</div>
      )}
      {actions && <div className="mt-4 flex flex-col gap-3 md:flex-row">{actions}</div>}
    </div>
  )
}
