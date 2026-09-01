import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'

// packages/design-system/specs/site-header.md

export interface SiteHeaderNavItem {
  /** Stable key. Never rendered. */
  id: string
  /** The visible label. Real text, always — there is no icon-only nav item (§9). */
  label: string
  /** Destination path, e.g. `/matches`. Also what `currentPath` is matched against (§4). */
  href: string
}

export interface SiteHeaderProps {
  /** The primary destinations, in the order they are shown. Required, and `[]` is a legitimate
   * value — the signed-out call site passes it deliberately (§5 empty). */
  items: readonly SiteHeaderNavItem[]
  /** The current pathname, e.g. `/matches/12345`. Absent → no item is marked current (§4). */
  currentPath?: string
  /** Where the wordmark links. Defaults to `/`. */
  brandHref?: string
  /** Target of `SkipLink`. Defaults to `#main-content`; see §9's call-site obligation (T442). */
  skipToContentHref?: string
  /** SPA navigation seam, exactly as `PlayerResultRow` and `MatchRow` already take it. */
  onNavigate?: (href: string) => void
  className?: string
}

// The wordmark's text is not a prop (§2a) — a caller that could override it could also break it.
const WORDMARK = 'aoe2-stats'

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring'

/** A destination is real only when both `label` and `href` are non-blank (§5 "error": a call-site
 * defect omits the item rather than rendering a dead link — the same choice `Footer` makes for an
 * absent href). */
function isRealItem(item: SiteHeaderNavItem): boolean {
  return item.label.trim() !== '' && item.href.trim() !== ''
}

/** §4's pure string rule, evaluated without a router this package does not depend on: exact
 * match, or a prefix match at a path-segment boundary (`href + '/'`), the longest `href` winning
 * a tie. `/` matches only exactly — otherwise it would be "current" on every page. No match, or no
 * `currentPath` at all, marks nothing (§5 empty, second case). */
function findCurrentItem(
  items: readonly SiteHeaderNavItem[],
  currentPath: string | undefined,
): SiteHeaderNavItem | undefined {
  if (!currentPath) return undefined
  let current: SiteHeaderNavItem | undefined
  for (const item of items) {
    const matches =
      item.href === currentPath || (item.href !== '/' && currentPath.startsWith(`${item.href}/`))
    if (matches && (!current || item.href.length > current.href.length)) current = item
  }
  return current
}

/** Site chrome (site-header.md), mounted once by the web shell (T442) so it renders on every
 * route. `SkipLink` and `Brand` are never conditional; `PrimaryNav` renders only when at least one
 * real item is supplied — the signed-out call site passes `[]` on purpose (§5 empty), and the
 * component never invents a placeholder strip in its place. Renders no image of any kind (§Asset
 * origin): the wordmark is a text glyph, never a logo. */
export function SiteHeader({
  items,
  currentPath,
  brandHref = '/',
  skipToContentHref = '#main-content',
  onNavigate,
  className,
}: SiteHeaderProps) {
  const realItems = items.filter(isRealItem)
  const current = findCurrentItem(realItems, currentPath)

  return (
    <header className={cx('border-b border-border bg-surface px-4 py-2 md:px-6', className)}>
      {/* The first focusable element on every page (§9). `sr-only`/`focus:not-sr-only` clips it
       * rather than removing it, so it never leaves the tab order the way `display: none` would —
       * it becomes visible, with the same ring every other part of this component shows, the
       * moment it takes focus. */}
      <a
        href={skipToContentHref}
        className={cx(
          'sr-only',
          'focus:not-sr-only focus:fixed focus:top-2 focus:left-4 focus:z-50 focus:rounded-md',
          'focus:border focus:border-border-strong focus:bg-surface-raised focus:px-3 focus:py-2',
          'focus:font-sans focus:text-sm focus:font-normal focus:text-text-primary',
          focusRing,
        )}
      >
        Skip to content
      </a>

      <div className="flex flex-col items-start gap-3 md:flex-row md:items-center md:gap-6">
        <a
          href={brandHref}
          onClick={createRowLinkClickHandler(brandHref, onNavigate)}
          className={cx(
            'font-display text-lg font-semibold tracking-tight text-text-primary hover:underline',
            focusRing,
          )}
        >
          {WORDMARK}
        </a>

        {realItems.length > 0 && (
          <nav aria-label="Primary">
            <ul className="flex flex-wrap gap-2">
              {realItems.map((item) => {
                const isCurrent = current?.id === item.id
                return (
                  <li key={item.id} className="flex flex-col">
                    <a
                      href={item.href}
                      aria-current={isCurrent ? 'page' : undefined}
                      onClick={createRowLinkClickHandler(item.href, onNavigate)}
                      className={cx(
                        'flex min-h-12 items-center justify-center rounded-md border border-transparent px-3',
                        'font-sans text-sm',
                        'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                        focusRing,
                        'hover:bg-surface-sunken hover:text-text-primary',
                        'active:border-border-strong active:bg-surface-sunken active:text-text-primary',
                        isCurrent
                          ? 'font-semibold text-text-primary'
                          : 'font-medium text-text-secondary',
                      )}
                    >
                      {item.label}
                    </a>
                    {/* The reserved current-route channel (§4, §7): every item renders this strip
                     * at the same height, so marking one item current shifts nothing else. */}
                    <span
                      aria-hidden="true"
                      className={cx('mt-1 h-0.5', isCurrent ? 'bg-accent' : 'bg-transparent')}
                    />
                  </li>
                )
              })}
            </ul>
          </nav>
        )}
      </div>
    </header>
  )
}
