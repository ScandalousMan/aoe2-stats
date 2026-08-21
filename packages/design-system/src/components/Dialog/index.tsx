import type { ReactNode } from 'react'
import { useEffect, useId, useRef } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import type { ButtonVariant } from '../Button'

// packages/design-system/specs/shared-primitives.md#Dialog

export interface DialogAction {
  label: ReactNode
  onClick?: () => void
  variant?: ButtonVariant
  disabled?: boolean
  loading?: boolean
  loadingLabel?: string
}

export interface DialogProps {
  heading: ReactNode
  /** Body content: plain paragraphs, an inline `Callout`, or both. */
  children?: ReactNode
  /** Rendered first, at `lg` and full width below `md`. Defaults to the `destructive` variant —
   * both call sites this primitive was extracted from (consent withdrawal, profile unlink) confirm
   * a consequential action, and a caller confirming something reversible passes its own `variant`. */
  primaryAction: DialogAction
  /** Rendered second. Its `onClick` is also what Escape calls: the accidental key must never be
   * the one that takes the consequential path (consent-step.md §9), so Escape is wired to the
   * cancelling action rather than exposed as a separate prop a caller could get backwards. */
  secondaryAction: DialogAction
  className?: string
}

/** A modal confirmation dialog: focus moves to the heading on open, Tab is trapped inside the
 * dialog while it is open, and Escape triggers `secondaryAction` — never `primaryAction`. Chrome is
 * a bottom sheet below `md` and a centred, boxed dialog from `md` up (tokens only: `bg-overlay`
 * backdrop, `bg-surface` fill, `shadow-modal` elevation). */
export function Dialog({
  heading,
  children,
  primaryAction,
  secondaryAction,
  className,
}: DialogProps) {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const secondaryOnClickRef = useRef(secondaryAction.onClick)
  secondaryOnClickRef.current = secondaryAction.onClick

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        secondaryOnClickRef.current?.()
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, a[href], input, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-overlay md:items-center">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className={cx(
          'w-full max-w-sm rounded-t-xl bg-surface p-6 shadow-modal md:rounded-xl',
          className,
        )}
      >
        <h2
          id={headingId}
          ref={headingRef}
          tabIndex={-1}
          className="font-display text-xl font-semibold text-text-primary"
        >
          {heading}
        </h2>

        {children && <div className="mt-3 font-sans text-sm text-text-secondary">{children}</div>}

        <div className="mt-6 flex flex-col gap-3 md:flex-row">
          <Button
            variant={primaryAction.variant ?? 'destructive'}
            size="lg"
            disabled={primaryAction.disabled}
            loading={primaryAction.loading}
            loadingLabel={primaryAction.loadingLabel}
            onClick={primaryAction.onClick}
            className="w-full md:w-auto"
          >
            {primaryAction.label}
          </Button>
          <Button
            variant={secondaryAction.variant ?? 'secondary'}
            size="lg"
            disabled={secondaryAction.disabled}
            loading={secondaryAction.loading}
            loadingLabel={secondaryAction.loadingLabel}
            onClick={secondaryAction.onClick}
            className="w-full md:w-auto"
          >
            {secondaryAction.label}
          </Button>
        </div>
      </div>
    </div>
  )
}
