import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/shared-primitives.md#StatValue
//
// "A loading StatValue never renders 0, – or --. In a stats tool a placeholder numeral read as
// real is the worst failure this design system can produce, and it is invisible in review because
// it looks fine." That rule drives every branch below: `status="loading"` renders a Skeleton and
// nothing else, `status="empty"` renders a secondary-colour em dash that can never be mistaken for
// a measured figure, and a stale-but-known value (a failed refresh) is expressed with the ordinary
// `status="default"` value plus a `secondaryLine` explaining the staleness — never a fourth,
// dimmer rendering of the number itself. Stale-and-labelled beats blank; blank beats wrong.

export type StatValueVariant = 'hero' | 'compact' | 'inline'
export type StatValueStatus = 'default' | 'loading' | 'empty'

export interface StatValueDelta {
  /** Sign is derived from the sign of this number: positive renders "+12" in `success`, negative
   * renders "−8" in `danger`. The character is the accessible name — never a rotated arrow. */
  value: number
  /** Pre-formatted magnitude, e.g. "12" for a delta of 12. Defaults to `Math.abs(value)`. */
  formatted?: string
}

export interface StatValueProps {
  label: ReactNode
  variant?: StatValueVariant
  status?: StatValueStatus
  /** Pre-formatted value text (this component does not localise numbers). Ignored when `status`
   * is `loading` or `empty`. */
  value?: ReactNode
  unit?: ReactNode
  delta?: StatValueDelta
  /** Measured-at timestamp, staleness notice, "Not ranked yet", or the reason a value is empty. */
  secondaryLine?: ReactNode
  /** Width of the loading skeleton, matching the footprint of the value that will arrive. */
  loadingWidthClassName?: string
  className?: string
}

const valueSize: Record<StatValueVariant, string> = {
  hero: 'text-2xl md:text-3xl',
  compact: 'text-lg',
  inline: 'text-md',
}

export function StatValue({
  label,
  variant = 'inline',
  status = 'default',
  value,
  unit,
  delta,
  secondaryLine,
  loadingWidthClassName = 'w-16',
  className,
}: StatValueProps) {
  return (
    <dl className={cx('flex flex-col', className)}>
      <dt className="font-sans text-sm text-text-secondary">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2">
        {status === 'loading' && (
          <Skeleton
            variant="number"
            className={cx(valueSize[variant], 'h-[1.2em]', loadingWidthClassName)}
          />
        )}
        {status === 'empty' && (
          <span
            className={cx(
              'font-mono font-semibold tracking-tight text-text-secondary',
              valueSize[variant],
            )}
          >
            —
          </span>
        )}
        {status === 'default' && (
          <>
            <span
              className={cx(
                'font-mono font-semibold tracking-tight text-text-primary',
                valueSize[variant],
              )}
            >
              {value}
            </span>
            {unit && <span className="font-sans text-sm text-text-secondary">{unit}</span>}
            {delta && <Delta delta={delta} />}
          </>
        )}
      </dd>
      {secondaryLine && (
        <span className="mt-1 font-sans text-xs text-text-secondary">{secondaryLine}</span>
      )}
    </dl>
  )
}

function Delta({ delta }: { delta: StatValueDelta }) {
  const positive = delta.value >= 0
  const magnitude = delta.formatted ?? String(Math.abs(delta.value))
  const sign = positive ? '+' : '−'
  return (
    <span
      className={cx('font-mono text-sm font-semibold', positive ? 'text-success' : 'text-danger')}
    >
      {sign}
      {magnitude}
    </span>
  )
}
