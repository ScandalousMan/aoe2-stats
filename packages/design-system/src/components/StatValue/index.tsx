import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/shared-primitives.md#StatValue
//
// "A loading StatValue never renders 0, – or --. In a stats tool a placeholder numeral read as
// real is the worst failure this design system can produce, and it is invisible in review because
// it looks fine." That rule drives every branch below: `status="loading"` renders a Skeleton and
// nothing else, `status="empty"` renders words in `text-secondary` at the value's own size, stating
// why the value has never been observed (T532, US4 scenario 3, SC-010) — never a punctuation mark
// a reader has to interpret — and a stale-but-known value (a failed refresh) is expressed with the
// ordinary `status="default"` value plus a `secondaryLine` explaining the staleness — never a
// fourth, dimmer rendering of the number itself. Stale-and-labelled beats blank; blank beats wrong.

export type StatValueVariant = 'hero' | 'compact' | 'inline'
export type StatValueStatus = 'default' | 'loading' | 'empty'

export interface StatValueDelta {
  /** Sign is derived from the sign of this number: positive renders "+12" in `success`, negative
   * renders "−8" in `danger`. The character is the accessible name — never a rotated arrow. */
  value: number
  /** Pre-formatted magnitude, e.g. "12" for a delta of 12. Defaults to `Math.abs(value)`. */
  formatted?: string
}

// T532: a generic, always-true default — this component cannot know *why* a value was never
// observed (never played this leaderboard, not yet rated, no matches in the selected range), so it
// never fabricates a specific claim. A caller who knows the reason states it via `emptyReason` or
// `secondaryLine` instead (see `StatValueProps` below).
const DEFAULT_EMPTY_REASON = 'No data yet'

export interface StatValueProps {
  label: ReactNode
  variant?: StatValueVariant
  status?: StatValueStatus
  /** Pre-formatted value text (this component does not localise numbers). Ignored when `status`
   * is `loading` or `empty`. */
  value?: ReactNode
  unit?: ReactNode
  delta?: StatValueDelta
  /** Measured-at timestamp, staleness notice, or (when `status` is not `empty`, or `emptyReason` is
   * also given) the reason a value is empty. T532: while `status="empty"` and `emptyReason` is
   * absent, this text is promoted into the value slot itself instead — see `emptyReason` — so it is
   * not repeated a second time down here. */
  secondaryLine?: ReactNode
  /** Shown in the value slot, in words, when `status` is `empty` (US4 acceptance scenario 3,
   * SC-010): replaces the value a reader would otherwise have to interpret a punctuation mark for.
   * The reason a value has never been observed is a fact only the caller has — never played this
   * leaderboard, not yet rated, no matches in the selected range — so `StatValue` never invents one.
   * Defaults to reusing `secondaryLine` when the caller already supplied one (existing call sites
   * already pass the reason there), and falls back to a generic, always-true "No data yet" when
   * neither is given. */
  emptyReason?: ReactNode
  /** Width of the loading skeleton, matching the footprint of the value that will arrive. */
  loadingWidthClassName?: string
  /** Whether this `StatValue` announces its own `loading` state as an ARIA-busy region (FR-054).
   * Defaults to `true`, correct for a `StatValue` used standalone — nothing else would announce it.
   * When several are composed into one loading column, row or table, exactly one ancestor region
   * must announce "busy", never each cell: every `StatValue` in that group must be given
   * `announceLoading={false}`, and the composing component owns a single `aria-busy="true"` on the
   * shared container instead (documented per composing component in
   * `packages/design-system/specs/shared-primitives.md#StatValue`). */
  announceLoading?: boolean
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
  emptyReason,
  loadingWidthClassName = 'w-16',
  announceLoading = true,
  className,
}: StatValueProps) {
  // T532: while empty, an explicit `emptyReason` always wins; absent that, a `secondaryLine` the
  // caller already supplied is reused as the value slot's own words instead of being shown twice.
  const reuseSecondaryLineAsReason =
    status === 'empty' && emptyReason == null && secondaryLine != null
  const resolvedEmptyReason = emptyReason ?? secondaryLine ?? DEFAULT_EMPTY_REASON

  return (
    <dl
      className={cx('flex flex-col', className)}
      aria-busy={status === 'loading' && announceLoading ? true : undefined}
    >
      <dt className="font-sans text-sm text-text-secondary">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2">
        {status === 'loading' && (
          // T528: closes an arbitrary length value. `1.2em` rode the font-size class beside it
          // (`valueSize[variant]`) to approximate one line's height at whichever variant's own
          // size. No `icon.json` step is the right token here: every icon step sets width *and*
          // height together, and this placeholder already takes its width from the caller's own
          // `loadingWidthClassName` — pairing a width-setting utility onto it would race that
          // prop for the same property. The nearest sanctioned utility is instead the ordinary
          // spacing scale (`h-6`, `1.5rem`/24px), matching `type-body`'s own line-height and the
          // `inline` variant's own text-md size exactly; `hero` and `compact` skeletons now
          // render at a fixed height rather than scaling with `1.2em` per variant, an accepted
          // trade-off recorded here rather than left as a silent behaviour change.
          <Skeleton
            variant="number"
            className={cx(valueSize[variant], 'h-6', loadingWidthClassName)}
          />
        )}
        {status === 'empty' && (
          // T532: words, not a punctuation mark — `type-supporting` (ordinary body/supporting
          // typography, never `type-identifier`: this is prose stating a reason, not a raw value
          // the product could not resolve to a name) at the value's own size, so the row keeps its
          // footprint, and `text-secondary` (not `font-semibold`/`tracking-tight`, both specific to
          // `type-numeric`'s digit treatment) so the empty state is visibly distinct from a measured
          // value in weight and typeface as well as in colour.
          <span className={cx('type-supporting text-text-secondary', valueSize[variant])}>
            {resolvedEmptyReason}
          </span>
        )}
        {status === 'default' && (
          <>
            <span
              className={cx(
                'type-numeric font-semibold tracking-tight text-text-primary',
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
      {secondaryLine && !reuseSecondaryLineAsReason && (
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
      className={cx(
        'type-numeric text-sm font-semibold',
        positive ? 'text-success' : 'text-danger',
      )}
    >
      {sign}
      {magnitude}
    </span>
  )
}
