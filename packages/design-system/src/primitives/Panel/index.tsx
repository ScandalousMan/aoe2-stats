import { Children, createContext, useContext, useId, type ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §7 (T544, FR-012, FR-013, FR-020). `Panel` owns
// the bounded surface — fill, hairline border, radius and elevation — and the caller may not choose
// any of the four: there is no elevation prop at all (`raised` is reserved for a whole screen's one
// focal surface, `SignInScreen`'s card, which a reusable surface cannot claim), and the radius is
// always `rounded-panel`, the role rather than a size.

// The one nesting rule (§7, "Surface, and the one nesting rule"): a `Panel` on a page draws
// `surface`; nested once inside another `Panel` it draws `surface-raised`, so the inner block reads
// as distinct from the outer one. There is no third surface token that keeps its distance from
// both, so a third level throws rather than silently reusing `surface-raised` again. The nesting
// level is read from context, never passed as a prop — a caller that could pass it could disagree
// with the page it is actually nested in.
const PanelDepthContext = createContext(0)

export type PanelDensity = 'dense' | 'prose'

export interface PanelProps {
  /** Which of the two surface classes this panel belongs to
   * (`packages/design-system/specs/README.md`, "Surface density"). Required, not defaulted: a
   * component picks exactly one class when its own spec is written, never at the reader's
   * discretion (structural-tier.md §3). */
  density: PanelDensity
  /** The panel's own optional heading, one level below its enclosing `Section`. A `Panel` with no
   * heading renders a plain `<div>`; with one, it renders a `<section>` with `aria-labelledby`
   * (structural-tier.md §7, Accessibility). */
  heading?: ReactNode
  /** Supporting line under the heading, in `text-secondary`. Only meaningful together with
   * `heading`. */
  description?: ReactNode
  /** The header's optional action row, beside the heading from `md` and wrapped below it at 375. */
  actions?: ReactNode
  /** A summary line or an action row under the body. */
  footer?: ReactNode
  /** Marks the panel `aria-busy="true"` once while its content is still arriving (FR-054) — never
   * per skeleton. The frame, its radius and its padding are retained regardless, so the loading and
   * loaded frames coincide exactly. */
  loading?: boolean
  /** The panel's body, stacked at the density's own internal step. A `Panel` given no children at
   * all renders nothing — no frame, no padding — which is what tells an intentionally empty surface
   * (pass an `EmptyState` here) apart from one nothing was ever given to (structural-tier.md §7,
   * "empty"). */
  children?: ReactNode
}

export function Panel({
  density,
  heading,
  description,
  actions,
  footer,
  loading = false,
  children,
}: PanelProps) {
  const depth = useContext(PanelDepthContext)
  if (depth >= 2) {
    throw new Error(
      'Panel: a second level of nesting is forbidden (structural-tier.md §7) — there is no third ' +
        'surface token that keeps its distance from both surface and surface-raised.',
    )
  }
  const headingId = useId()

  // No children at all: the panel renders nothing (structural-tier.md §7, "empty"). A
  // caller-supplied empty *condition* still passes children (an `EmptyState`), which reaches the
  // frame below instead.
  if (Children.count(children) === 0) {
    return null
  }

  const Tag = heading ? 'section' : 'div'
  const hasHeader = Boolean(heading) || Boolean(description) || Boolean(actions)

  return (
    <PanelDepthContext.Provider value={depth + 1}>
      <Tag
        {...(heading ? { 'aria-labelledby': headingId } : {})}
        aria-busy={loading || undefined}
        className={cx(
          'flex flex-col',
          'rounded-panel border-hairline border-border',
          depth === 0 ? 'bg-surface' : 'bg-surface-raised',
          density === 'dense' ? 'p-4' : 'p-6 md:p-8',
        )}
      >
        {hasHeader && (
          <div className="mb-3 flex flex-col gap-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              {heading && (
                <h3 id={headingId} className="type-display text-xl font-semibold text-text-primary">
                  {heading}
                </h3>
              )}
              {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
            </div>
            {description && (
              <p className="type-supporting text-sm text-text-secondary">{description}</p>
            )}
          </div>
        )}
        <div className={cx('flex flex-col', density === 'dense' ? 'gap-3' : 'gap-4 max-w-measure')}>
          {children}
        </div>
        {footer && <div className="mt-4 flex flex-wrap items-center gap-3">{footer}</div>}
      </Tag>
    </PanelDepthContext.Provider>
  )
}
