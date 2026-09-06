import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Callout } from '../Callout'
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
  /** The item action currently reported as failed. Renders a danger `Callout` inside the surface
   * below that item; the menu stays open. */
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
          'inline-flex h-10 items-center gap-2 rounded-control border border-border-strong bg-surface px-4 font-sans text-sm',
          'transition-colors duration-120 ease-standard',
          'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
          isEmpty
            ? 'cursor-default text-text-disabled'
            : 'text-text-primary hover:bg-surface-sunken',
        )}
      >
        {triggerLabel}
      </button>

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
                    'flex min-h-12 w-full items-center px-4 font-sans text-sm text-text-primary',
                    'transition-colors duration-120 ease-standard hover:bg-surface-sunken',
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

  return (
    <div>
      <button
        type="button"
        ref={ref as never}
        role={role}
        aria-checked={variant === 'selection' ? Boolean(item.checked) : undefined}
        aria-disabled={item.disabled || item.loading || undefined}
        aria-busy={item.loading || undefined}
        tabIndex={tabIndex}
        onKeyDown={onKeyDown}
        onClick={onActivate}
        className={cx(
          'flex min-h-12 w-full items-center justify-between gap-3 px-4 text-left font-sans text-sm',
          'transition-colors duration-120 ease-standard',
          'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring',
          item.disabled || item.loading
            ? 'cursor-default text-text-disabled'
            : 'text-text-primary hover:bg-surface-sunken',
        )}
      >
        <span className="flex flex-col">
          <span>{item.label}</span>
          {(item.secondaryLine || (item.disabled && item.disabledReason)) && (
            <span className="text-xs text-text-secondary">
              {item.disabled ? item.disabledReason : item.secondaryLine}
            </span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {item.badge}
          {item.loading && <Spinner />}
        </span>
      </button>
      {showError && (
        <div className="px-4 pt-2">
          <Callout tone="danger" heading={errorMessage ?? 'That action failed'} headingLevel={3} />
        </div>
      )}
    </div>
  )
}
