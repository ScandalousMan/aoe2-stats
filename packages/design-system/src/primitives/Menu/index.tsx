import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Spinner } from '../../lib/Spinner'

// packages/design-system/specs/shared-primitives.md#Menu

export type MenuVariant = 'selection' | 'actions'

export interface MenuItem {
  id: string
  label: ReactNode
  secondaryLine?: ReactNode
  badge?: ReactNode
  /** `selection` variant only: this item is the current one. */
  checked?: boolean
  disabled?: boolean
  disabledReason?: ReactNode
  loading?: boolean
  onSelect?: () => void
}

export interface MenuFooterItem {
  id: string
  label: ReactNode
  onSelect?: () => void
}

export interface MenuProps {
  variant: MenuVariant
  triggerLabel: ReactNode
  /** Overrides the trigger's accessible name when the visible label alone should not be it — e.g.
   * the profile switcher's trigger must be announced with the word "profile" in its name
   * (profile-summary.md, §Accessibility) even though the visible label is just the alias. */
  triggerAriaLabel?: string
  items: MenuItem[]
  footerItem?: MenuFooterItem
  /** The item action currently reported as failed. Renders a danger-toned message inside the
   * surface below that item — visually a `Callout`, though not the component itself (T559: `role=
   * "menu"`'s required owned elements exclude `role="alert"`/`role="status"`, see `MenuItemRow`) —
   * and announces it assertively via a dedicated live region outside `role="menu"`. The menu stays
   * open. */
  errorItemId?: string | null
  errorMessage?: ReactNode
  className?: string
}

/** A menu with no items does not open; the trigger is `aria-disabled` with a reason (shared-
 * primitives.md, §empty). Below `md` it opens as a full-width bottom sheet; from `md` up, a
 * popover anchored to the trigger — one DOM tree, restructured by CSS at the breakpoint, per the
 * same "never both layouts" rule ProfileSummary states explicitly for its ratings table. */
export function Menu({
  variant,
  triggerLabel,
  triggerAriaLabel,
  items,
  footerItem,
  errorItemId,
  errorMessage,
  className,
}: MenuProps) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const itemRefs = useRef<Array<HTMLElement | null>>([])
  const surfaceId = useId()
  const isSheet = !useBreakpoint('md')
  const isEmpty = items.length === 0

  const allIds = useMemo(() => items.map((item) => item.id), [items])

  useEffect(() => {
    if (!open) return
    const checkedIndex = items.findIndex((item) => item.checked)
    setActiveIndex(checkedIndex >= 0 ? checkedIndex : 0)
  }, [open, items])

  useEffect(() => {
    if (open) itemRefs.current[activeIndex]?.focus()
  }, [open, activeIndex])

  function close(returnFocus = true) {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }

  function moveTo(index: number) {
    const count = allIds.length + (footerItem ? 1 : 0)
    const next = ((index % count) + count) % count
    setActiveIndex(next)
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (isEmpty) return
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
    }
  }

  function onItemKeyDown(event: KeyboardEvent<HTMLElement>, index: number) {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        moveTo(index + 1)
        break
      case 'ArrowUp':
        event.preventDefault()
        moveTo(index - 1)
        break
      case 'Home':
        event.preventDefault()
        moveTo(0)
        break
      case 'End':
        event.preventDefault()
        moveTo(allIds.length + (footerItem ? 1 : 0) - 1)
        break
      case 'Escape':
        event.preventDefault()
        close()
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  return (
    <div className={cx('relative inline-block', className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-disabled={isEmpty || undefined}
        aria-label={triggerAriaLabel}
        onClick={() => !isEmpty && setOpen((value) => !value)}
        onKeyDown={onTriggerKeyDown}
        className={cx(
          // T561 (FR-018/FR-019, shared-primitives.md §Sizes): this trigger is reachable on every
          // viewport including 375 — there is no pointer-only call site — so it clears the 44px
          // touch floor unconditionally at `min-h-12` (48px), the same size `Menu`'s own items
          // already use, rather than `Button`'s pointer-only `md` (40px) it used to copy. `min-h-`,
          // not `h-`, so a caller's `triggerLabel` that wraps onto two lines (a long alias, at a
          // narrow width) still grows the box instead of clipping it.
          'inline-flex min-h-12 items-center gap-2 rounded-control border border-border-strong bg-surface px-4 font-sans text-sm',
          // T560 (FR-038): this trigger paints the same resting/border recipe as `Button`'s
          // `secondary` variant (`bg-surface`, `border-border-strong`) but had none of its
          // active/reduced-motion behaviour — same category, now the same response.
          'transition-colors duration-120 ease-standard motion-reduce:duration-0',
          'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
          isEmpty
            ? 'cursor-default text-text-disabled'
            : 'text-text-primary hover:bg-surface-sunken active:bg-surface-sunken active:border-border-strong',
        )}
      >
        {triggerLabel}
      </button>

      {/* T559 (FR-057): the failure text visible on the item below (`MenuItemRow`'s own paragraph)
          carries no ARIA role of its own — a `role="alert"` region is not one of `menu`'s required
          owned elements (`group`/`menuitem`/`menuitemcheckbox`/`menuitemradio`/`separator`), and
          nesting one inside `role="menu"` is exactly the aria-required-children violation this
          region exists to remove (confirmed with axe-core directly: neither a wrapping
          `role="presentation"` nor `role="group"` shields a role-bearing or focusable descendant —
          axe's `getOwnedRoles` flattens straight through both looking for the ancestor's allowed
          child roles). This region sits outside `role="menu"` instead, mounted for the component's
          whole lifetime so a screen reader has already registered it before its text ever changes —
          the ordinary `aria-live` reliability rule — and is the sole carrier of the assertive
          announcement `role="alert"` would otherwise have given for free. */}
      <div aria-live="assertive" className="sr-only">
        {errorItemId ? (errorMessage ?? 'That action failed') : ''}
      </div>

      {open && !isEmpty && (
        <>
          {isSheet && (
            <div
              className="fixed inset-0 z-40 bg-overlay"
              aria-hidden="true"
              onClick={() => close()}
            />
          )}
          <div
            id={surfaceId}
            role="menu"
            className={cx(
              'z-50 flex flex-col gap-2 rounded-overlay border border-border bg-surface-raised py-2 shadow-overlay',
              isSheet
                ? // T528: `max-h-sheet` — a viewport ceiling on a floating surface, not a token
                  // gap. Owned by the elevation contract (`build-tokens.mjs`'s
                  // `elevationUtilityBlocks`, README's Elevation section), never an arbitrary
                  // `max-h-[80vh]` bracket.
                  'fixed inset-x-0 bottom-0 max-h-sheet overflow-y-auto rounded-b-none'
                : 'absolute left-0 mt-2 min-w-64 max-w-sm',
            )}
          >
            {items.map((item, index) => (
              <MenuItemRow
                key={item.id}
                item={item}
                variant={variant}
                ref={(node) => {
                  itemRefs.current[index] = node
                }}
                tabIndex={activeIndex === index ? 0 : -1}
                onKeyDown={(event) => onItemKeyDown(event, index)}
                onActivate={() => {
                  if (item.disabled || item.loading) return
                  item.onSelect?.()
                  if (variant === 'actions') close()
                }}
                showError={errorItemId === item.id}
                errorMessage={errorMessage}
              />
            ))}
            {footerItem && (
              <div className="mt-1 border-t border-border pt-2">
                <button
                  type="button"
                  role="menuitem"
                  ref={(node) => {
                    itemRefs.current[allIds.length] = node
                  }}
                  tabIndex={activeIndex === allIds.length ? 0 : -1}
                  onKeyDown={(event) => onItemKeyDown(event, allIds.length)}
                  onClick={() => {
                    footerItem.onSelect?.()
                    close()
                  }}
                  className={cx(
                    'flex min-h-12 w-full items-center border-l-2 border-l-transparent px-4 font-sans text-sm text-text-primary',
                    // T560 (FR-038): a `role="menuitem"`, same category as `MenuItemRow` below,
                    // so it gets the same active state (shared-primitives.md#Menu "active" — fill
                    // plus a `border-strong` boundary on the inline-start edge) and the same
                    // reduced-motion resting frame, neither of which it had.
                    'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                    'hover:bg-surface-sunken active:border-l-border-strong active:bg-surface-sunken',
                    'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  )}
                >
                  {footerItem.label}
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// T572 scenario 9 remediation (defect 1): shared-primitives.md#Menu's "selection" state, as T570
// left it, made the checked item's still-image mark entirely the caller's `badge` slot — "`Menu`
// itself does not decide what that slot contains." That is now the wrong shape: a reader given only
// the built Storybook could not tell `Menu/Selection`, `Menu/Profile Switcher` and
// `Menu/Focus Visible` apart (`ImageChops.difference(...).getbbox() is None` for both pairs), because
// the one thing that actually changes row to row — `aria-checked` — painted nothing of its own; the
// blue ring any of those three shows is the *focus* ring, not a selection mark, and a caller who
// forgets to supply a badge (`Menu`'s own `Empty`/`ActionsWithDisabledItem` stories carry no badge
// at all, and neither variant enforces one) ships a selected row indistinguishable from an
// unselected one. This is exactly the "a decision a caller may not write has to live somewhere that
// is not a caller" shape T556 already named for a different component — so the mark now lives here,
// unconditionally, for every `selection`-variant item regardless of whether a caller also supplies a
// trailing badge.
//
// A leading checkmark glyph, not a fill or ink change (README rule 4, and FR-037's still-image
// rule): a shape that is present or invisible, reserving the same width either way — the identical
// technique `SiteHeader`'s current-route underline already uses for the same reason
// (`src/composites/SiteHeader/index.tsx`) — so every item's label stays aligned whether or not that
// item is the checked one, and a still image shows the shape itself, not merely a hue. Positioned at
// the item's *leading* edge, opposite the trailing `badge`/`Spinner` slot, so it cannot occupy the
// same pixels as a caller-supplied `<Badge>Current</Badge>` (`ProfileSummary`'s profile switcher,
// `SiteHeader`'s `ThemeControl`) — the two coexist as two different signals (a shape versus a word)
// rather than one duplicating the other. A generic checkmark, not a game asset (README rule 3: no
// licence record needed — this is an original, geometric glyph, the same class of mark
// `FavouriteToggle`'s `StateGlyph` already is).
function SelectionGlyph({ checked }: { checked: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className={cx('icon-sm shrink-0', checked ? undefined : 'invisible')}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8.5 6.5 12 13 4.5" />
    </svg>
  )
}

interface MenuItemRowProps {
  item: MenuItem
  variant: MenuVariant
  tabIndex: number
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void
  onActivate: () => void
  showError: boolean
  errorMessage?: ReactNode
}

function MenuItemRow({
  item,
  variant,
  tabIndex,
  onKeyDown,
  onActivate,
  showError,
  errorMessage,
  ref,
}: MenuItemRowProps & { ref: (node: HTMLElement | null) => void }) {
  const role = variant === 'selection' ? 'menuitemradio' : 'menuitem'
  // T559: an id for the plain error paragraph below, so the button that failed still names it via
  // `aria-describedby` — an ordinary reference, not a containment relationship, so it costs nothing
  // in the `role="menu"` owned-children accounting (`aria-required-children` never inspects what an
  // id-ref points at, only DOM containment). The always-mounted live region in `Menu` itself
  // (above) carries the assertive announcement; this is the on-focus discoverability half.
  const errorId = useId()

  return (
    <div>
      <button
        type="button"
        ref={ref as never}
        role={role}
        aria-checked={variant === 'selection' ? Boolean(item.checked) : undefined}
        aria-disabled={item.disabled || item.loading || undefined}
        aria-busy={item.loading || undefined}
        aria-describedby={showError ? errorId : undefined}
        tabIndex={tabIndex}
        onKeyDown={onKeyDown}
        onClick={onActivate}
        className={cx(
          'flex min-h-12 w-full items-center justify-between gap-3 border-l-2 border-l-transparent px-4 text-left font-sans text-sm',
          // T560 (FR-038): shared-primitives.md#Menu documents "active — item fill
          // `surface-sunken` with boundary `border-strong` on the inline-start edge", never
          // built. `border-l-transparent` at rest reserves the width so the border does not shift
          // the label when it turns solid on press. `motion-reduce:duration-0` closes README
          // rule 5's gap, present on every other transition in the system but missing here.
          'transition-colors duration-120 ease-standard motion-reduce:duration-0',
          'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring',
          item.disabled || item.loading
            ? 'cursor-default text-text-disabled'
            : 'text-text-primary hover:bg-surface-sunken active:border-l-border-strong active:bg-surface-sunken',
        )}
      >
        <span className="flex items-center gap-3">
          {variant === 'selection' && <SelectionGlyph checked={Boolean(item.checked)} />}
          <span className="flex flex-col">
            <span>{item.label}</span>
            {(item.secondaryLine || (item.disabled && item.disabledReason)) && (
              <span className="text-xs text-text-secondary">
                {item.disabled ? item.disabledReason : item.secondaryLine}
              </span>
            )}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {item.badge}
          {item.loading && <Spinner />}
        </span>
      </button>
      {showError && (
        <div className="px-4 pt-2">
          {/* T559 (FR-057): visually a danger `Callout` (same tone-stripe and heading treatment),
              but deliberately not the `Callout` primitive itself — `Callout` always carries
              `role="alert"`/`role="status"`, `aria-labelledby` and a focusable (`tabIndex={-1}`)
              heading, and every one of those three independently makes it a disallowed owned
              element of `role="menu"` per `aria-required-children` (confirmed with axe-core: a
              bare, roleless, non-focusable paragraph is the only shape that survives nested here —
              see `Menu`'s own live region above for the announcement `role="alert"` would have
              given). A `<p>`, not a heading tag: this is a transient failure message inside a
              widget, not a document-outline heading, and a native heading tag carries an implicit
              ARIA heading role that trips the same check even with no attributes on it at all. */}
          <p
            id={errorId}
            className="rounded-panel border-l-2 border-danger bg-surface-raised p-4 font-sans text-md font-semibold text-danger md:p-5"
          >
            {errorMessage ?? 'That action failed'}
          </p>
        </div>
      )}
    </div>
  )
}
