import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §5 (T543, FR-020, FR-021).
// The one primitive that removes the nested-`<main>` defect from the live product (contracts/
// 005-design-system-foundations/structural-tier.md): after the retrofit (phase 5) no route
// declares a landmark, a width or a page padding of its own — `Page` is the only place any of the
// three is expressed. The retrofit itself, and the removal of `apps/web/src/routes/__root.tsx`'s
// own `<main>`, are T551/T552's; this component only has to exist and be correct standing alone.

/** The closed three-value width vocabulary (`tokens/size.json`, closes DS-6). A route chooses one
 * of these; there is no fourth width and no caller-supplied max-width class. */
export type PageWidth = 'page' | 'panel' | 'measure'

export interface PageProps {
  /** The route's only `<h1>`. Required: a page with no heading is a page a screen-reader user
   * cannot orient in, and leaving the heading to each route is how the nested-landmark defect
   * happened in the first place (structural-tier.md §5). */
  title: ReactNode
  /** Visually hides the title while it stays in the accessibility tree — the sole escape for a
   * route whose title is already carried by a large visible element. There is no third option. */
  titleHidden?: boolean
  /** Supporting line under the title, in `text-secondary`. */
  description?: ReactNode
  /** The header's optional action row — the one thing a caller may place beside the title. */
  actions?: ReactNode
  /** `page` (default) for data views, `panel` for a single-column form or result column, `measure`
   * for continuous reading. A caller may not write a max-width class instead (FR-021). */
  width?: PageWidth
  /** Marks the section stack `aria-busy="true"` once for the whole region while this route's data
   * is still arriving (FR-054) — never per skeleton. The header renders immediately regardless:
   * the title is known before the request resolves and withholding it costs the reader their
   * orientation. There is no full-page spinner. */
  loading?: boolean
  /** The route's `Section`s (or, while it fails or has nothing to show, one `ErrorState` or one
   * `EmptyState`) — separated from each other by the between-sections rhythm step. Composing which
   * of those to render is the caller's decision; `Page` renders whatever it is given. */
  children?: ReactNode
}

const widthClasses: Record<PageWidth, string> = {
  page: 'max-w-page',
  panel: 'max-w-panel',
  measure: 'max-w-measure',
}

// The landmark's own focus ring (structural-tier.md §5, "focus-visible"): shown only when the
// skip link sends focus here, never on a pointer click, which is exactly what `:focus-visible`
// means. `__root.tsx`'s `<main>` carries no ring at all today — this closes that gap rather than
// only relocating it.
const landmarkFocusRing =
  'outline-none focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

export function Page({
  title,
  titleHidden = false,
  description,
  actions,
  width = 'page',
  loading = false,
  children,
}: PageProps) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className={cx('min-h-svh bg-background', landmarkFocusRing)}
    >
      <div
        className={cx('mx-auto flex flex-col gap-6 px-4 py-6 md:px-6 md:py-8', widthClasses[width])}
      >
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h1
              className={cx(
                'type-display text-3xl font-semibold tracking-tight text-text-primary',
                titleHidden && 'sr-only',
              )}
            >
              {title}
            </h1>
            {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
          </div>
          {description && <p className="type-body text-md text-text-secondary">{description}</p>}
        </div>
        <div className="flex flex-col gap-8" aria-busy={loading || undefined}>
          {children}
        </div>
      </div>
    </main>
  )
}
