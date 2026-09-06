import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import { Badge } from '../../primitives/Badge'
import { Menu, type MenuItem } from '../../primitives/Menu'
import { ThemeProvider, useTheme, type Theme } from '../../theme'

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

// The three states this control's trigger reports, keyed by `override` where `null` reads as
// "system" (§ThemeControl). Fixed here, once, so the trigger label, the menu items and the tests
// all draw from the same three words.
const THEME_OPTION_LABEL: Record<'system' | Theme, string> = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
}

/** The one control in this package permitted to read the active theme (FR-014; the standing
 * exemption itself is recorded in `specs/README.md` by T536, not restated here). Three states,
 * never two: "system" is a real, reachable choice, not just the absence of one, so a reader who
 * has never overridden can always get back to following their OS rather than a two-state flip
 * quietly turning a "no preference" reader into someone with a permanent override.
 *
 * Reuses `Menu`'s `selection` variant — `role="menu"` / `menuitemradio` / `aria-checked` — rather
 * than inventing a second "choose one of a few named things" pattern: it is the one this package
 * already has (`ProfileSummary`'s profile switcher), and the checked item carries a `Badge` too,
 * per that component's own acceptance bar ("marked by text or a `Badge`, not by colour alone").
 *
 * Owns its own `ThemeProvider` rather than requiring the application shell to mount one: `useTheme`
 * has exactly one sanctioned consumer today — this control — so the provider travels with it
 * instead of asking every host of `SiteHeader` to also wire one up. It reads `document`'s already-
 * painted `data-theme` attribute on mount (`apps/web/index.html`, T533), so nesting it here changes
 * nothing about which theme first paints. */
function ThemeControl({ className }: { className?: string }) {
  return (
    <ThemeProvider>
      <ThemeMenu className={className} />
    </ThemeProvider>
  )
}

function ThemeMenu({ className }: { className?: string }) {
  const { override, setOverride, clearOverride } = useTheme()
  const current: 'system' | Theme = override ?? 'system'

  function markedItem(option: 'system' | Theme, onSelect: () => void): MenuItem {
    const checked = current === option
    return {
      id: option,
      label: THEME_OPTION_LABEL[option],
      checked,
      badge: checked ? <Badge>Current</Badge> : undefined,
      onSelect,
    }
  }

  const items: MenuItem[] = [
    markedItem('system', clearOverride),
    markedItem('light', () => setOverride('light')),
    markedItem('dark', () => setOverride('dark')),
  ]

  return (
    <Menu
      variant="selection"
      triggerLabel={
        <>
          Theme: {THEME_OPTION_LABEL[current]} <span aria-hidden="true">▾</span>
        </>
      }
      items={items}
      className={className}
    />
  )
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
          'focus:not-sr-only focus:fixed focus:top-2 focus:left-4 focus:z-50 focus:rounded-control',
          // T561 (FR-018/FR-019): `py-2` (8px each side) plus this text's own `text-sm` line-height
          // (20px, `tokens/font.json`) totals 38px, short of the 44px floor — `py-3` (12px each
          // side) clears it at 44px content height before the 1px focus border on each edge. Only
          // reachable once focused, but reachable by touch then (a tap after landing here via
          // switch/voice control, not only a hardware keyboard), so it owes the same floor as every
          // other touch-reachable control (site-header.md §9's "`SkipLink` and `Brand` clear it by
          // their own padding-block").
          'focus:border focus:border-border-strong focus:bg-surface-raised focus:px-3 focus:py-3',
          'focus:font-sans focus:text-sm focus:font-normal focus:text-text-primary',
          focusRing,
        )}
      >
        Skip to content
      </a>

      {/* The outer row places `ThemeControl` at the inline-end at every viewport — including 375,
       * beside `Brand` rather than beneath the wrapped nav — because it is present regardless of
       * whether there are any nav items at all (§ThemeControl is never conditional, unlike
       * `PrimaryNav`). `items-start` keeps it aligned with `Brand`'s row when the inner group
       * stacks at 375; `md:items-center` matches the inner group's own row alignment from `md`. */}
      <div className="flex items-start justify-between gap-3 md:items-center">
        <div className="flex flex-col items-start gap-3 md:flex-row md:items-center md:gap-6">
          <a
            href={brandHref}
            onClick={createRowLinkClickHandler(brandHref, onNavigate)}
            className={cx(
              // T561 (FR-018/FR-019): carried no padding of its own, so it measured 24px tall at
              // 375 and 1280 — the 48px site-header.md §9 credits it with only ever came from the
              // row's own height at `md`, incidentally, never from this link. `inline-flex
              // items-center` turns the vertical padding below into real box height (an `inline`
              // anchor's own padding-block does not reliably grow its hit area the way a flex
              // item's does); `py-3` (12px each side) plus `text-lg`'s own line-height (24px,
              // `tokens/font.json`) totals 48px, clearing the 44px floor with room, on every route
              // this is mounted on (§9's own claim, now true in code, not only in prose).
              'inline-flex items-center py-3 font-display text-lg font-semibold tracking-tight text-text-primary hover:underline',
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
                          'flex min-h-12 items-center justify-center rounded-control border border-transparent px-3',
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

        <ThemeControl className="shrink-0" />
      </div>
    </header>
  )
}
