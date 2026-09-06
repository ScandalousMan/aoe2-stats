import { createContext, useContext, useId, type ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §6 (T544, FR-020, FR-008). `Section` owns two
// things a caller may not: the space between the components stacked inside it (the
// `between-components` rhythm step, `space.json`'s `rhythm` group), and its own heading level. The
// space *between* one `Section` and the next belongs to `Page`'s section stack (§2, §5) — `Section`
// does not add an outer margin of its own, so composing it inside `Page` never doubles the gap.

// Heading level is derived from nesting depth, never passed as a prop (structural-tier.md §6): a
// hand-passed level could disagree with where the `Section` actually sits, and a level derived from
// depth cannot skip one the way a hand-passed one can. Depth 0 (no `Section` ancestor) renders
// `<h2>`; depth 1 (one `Section` ancestor) renders `<h3>`. A second level of nesting is forbidden —
// a page needing an `<h4>` is a page that should be two routes — and rendering a third-level
// `Section` throws rather than silently producing a heading level nothing above it chose.
const SectionDepthContext = createContext(0)

export interface SectionProps {
  /** The section's own heading. Required: an unlabelled `<section>` announces nothing to a screen
   * reader, worse than a `<div>` — there is no headingless variant (structural-tier.md §6). */
  heading: ReactNode
  /** Renders the heading visually hidden while it stays in the accessibility tree — the escape
   * hatch for a heading that would be visual noise. There is no third option. */
  headingHidden?: boolean
  /** Supporting line under the heading, in `text-secondary`. */
  description?: ReactNode
  /** The header's optional action row, reached in the reading order after the heading and before
   * the body. */
  actions?: ReactNode
  /** Marks the body `aria-busy="true"` once for the whole region (FR-054) — never per skeleton.
   * The heading renders immediately regardless and never becomes a skeleton itself. */
  loading?: boolean
  /** The section's own components (or, while it fails or has nothing to show, one `ErrorState` or
   * one `EmptyState`), stacked at the between-components step. A nested `Section` is also valid
   * content, one level deep only. */
  children?: ReactNode
}

export function Section({
  heading,
  headingHidden = false,
  description,
  actions,
  loading = false,
  children,
}: SectionProps) {
  const depth = useContext(SectionDepthContext)
  if (depth >= 2) {
    throw new Error(
      'Section: a second level of nesting is forbidden (structural-tier.md §6) — a page needing ' +
        'a third heading level should be split into two routes instead.',
    )
  }
  const headingId = useId()
  const HeadingTag = depth === 0 ? 'h2' : 'h3'

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <HeadingTag
            id={headingId}
            className={cx(
              'type-display font-semibold text-text-primary',
              depth === 0 ? 'text-2xl tracking-tight' : 'text-xl',
              headingHidden && 'sr-only',
            )}
          >
            {heading}
          </HeadingTag>
          {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
        </div>
        {description && (
          <p className="type-supporting text-sm text-text-secondary">{description}</p>
        )}
      </div>
      <div className="flex flex-col gap-6" aria-busy={loading || undefined}>
        <SectionDepthContext.Provider value={depth + 1}>{children}</SectionDepthContext.Provider>
      </div>
    </section>
  )
}
