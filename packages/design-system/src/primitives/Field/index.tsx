import { cloneElement, useEffect, useId, useRef } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §11 (T547, FR-025, FR-053).
// Contract (contracts/005-design-system-foundations/structural-tier.md): `Field` owns the label,
// hint and error associations and the error's text; the caller supplies the control (an <input>,
// <select> or <textarea>) and may not associate a label by hand — there is no `htmlFor` or
// `aria-describedby` for a caller to get wrong, because `Field` is the only thing that renders the
// <label> and the only thing that writes those attributes onto the control.

export type FieldSize = 'md' | 'lg'

/** The four attributes `Field` writes onto the cloned control. A caller may set any of them on the
 * child element it passes in — `Field` overwrites all four, which is the mechanism that makes "a
 * caller may not associate a label by hand" true rather than merely advised. `aria-busy` while
 * `loading` is carried by the field wrapper instead, once for the region rather than per element
 * (structural-tier.md §11, "loading"). */
export interface FieldControlProps {
  id?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
  disabled?: boolean
  className?: string
}

export interface FieldProps {
  /** The field's name. Always a real, visible `<label>` — never a placeholder standing in for
   * one, which disappears the moment the reader types and is absent exactly when they need it
   * (structural-tier.md §11, "empty"). */
  label: ReactNode
  /** Visually hides the label while it stays in the accessibility tree. Permitted only where an
   * adjacent visible element already names the control — the search field beside a visible
   * "Search" button is the shipping case. Not a way to make a form look cleaner. */
  labelHidden?: boolean
  /** Supporting text. Always rendered when present, never revealed only on hover (FR-039) — a
   * fact reachable by a mouse alone is unreachable by touch or keyboard. */
  hint?: ReactNode
  /** The error, as a complete sentence naming the field ("Profile id — enter digits only"), so it
   * reads as a statement on its own rather than needing the label read first. `undefined` means no
   * error — an empty value is never, on its own, an error (structural-tier.md §11, "empty"): a
   * required field that has never been touched shows its default paint and errors on blur or
   * submit, never on first render.
   *
   * Conveyed in text as well as in colour (FR-025): the sentence is the signal, and it stays
   * legible with colour removed. Announced to assistive technology only when it transitions from
   * absent to present *after* `Field`'s first render — an error already present at first paint is
   * not, because announcing it there would double the page's own initial announcement (FR-053). */
  error?: ReactNode
  /** `md` (default, pointer-only) or `lg` — the control height matched to `Button`'s so a field
   * and its submit button sit on one line at the same height (structural-tier.md §11). A field
   * reachable on a touch viewport renders at `lg`, which clears the 44px touch floor. The one
   * property of the control's own box `Field` decides on the caller's behalf, because the caller
   * does not know the field's size vocabulary. */
  size?: FieldSize
  /** Forwarded to the control alongside the generated association attributes. A caller sets
   * `disabled` here, never on the control directly, so the two can never disagree. */
  disabled?: boolean
  /** The control is disabled and the field carries `aria-busy="true"`; the label and hint stay at
   * full contrast and neither is replaced by a skeleton — a form that dissolves into grey blocks
   * while submitting has lost the reader's place in it (structural-tier.md §11, "loading"). */
  loading?: boolean
  /** Overrides the generated id. Never how the label association is made — `Field` writes
   * `htmlFor` either way — only a way to keep a stable id across renders. */
  id?: string
  className?: string
  /** The control: an `<input>`, `<select>`, `<textarea>`, or a component that forwards `id`,
   * `aria-describedby`, `aria-invalid` and `disabled` to one of those. `Field` clones it to inject
   * those four attributes and the size's height utility — it does not render the control itself
   * (structural-tier.md §11 anatomy). */
  children: ReactElement<FieldControlProps>
}

const sizeClasses: Record<FieldSize, string> = {
  md: 'h-10',
  lg: 'h-12',
}

/** Puts a control, its label, its hint and its error together so they cannot come apart, and so a
 * reader who cannot see colour still knows which control failed and why. */
export function Field({
  label,
  labelHidden = false,
  hint,
  error,
  size = 'md',
  disabled = false,
  loading = false,
  id,
  className,
  children,
}: FieldProps) {
  const generatedId = useId()
  const hintId = useId()
  const errorId = useId()
  const controlId = id ?? generatedId

  const hasError = Boolean(error)
  const isDisabled = disabled || loading

  // FR-053: an error announced only on the render where it *transitions* from absent to present,
  // never on the render where `Field` first mounts already carrying one. `previousHasErrorRef`
  // starts `undefined` (no prior render exists yet), so the very first render can never satisfy
  // `previousHasErrorRef.current === false` and never gets `role="alert"` — exactly the "present
  // at first paint" case FR-053 excludes. The effect below records this render's error state
  // *after* it commits, so the next render reads it as "previous". A screen reader announces the
  // node once, on the transition; a re-render with the same error unchanged is not a new
  // occurrence and stops carrying the role, which is also what stops it announcing itself on every
  // unrelated re-render of the surrounding form.
  const previousHasErrorRef = useRef<boolean | undefined>(undefined)
  const announceError = previousHasErrorRef.current === false && hasError

  useEffect(() => {
    previousHasErrorRef.current = hasError
  })

  const describedBy = [hint ? hintId : null, hasError ? errorId : null].filter(Boolean).join(' ')

  // `aria-busy` is set once, on the field wrapper below — never on the control as well
  // (structural-tier.md §11, "loading"; FR-054's "announced once for a region rather than once
  // per element" applied to a single field's own two elements).
  const control = cloneElement(children, {
    id: controlId,
    'aria-describedby': describedBy || undefined,
    'aria-invalid': hasError ? true : undefined,
    disabled: isDisabled || children.props.disabled,
    className: cx(children.props.className, sizeClasses[size]),
  })

  return (
    <div className={cx('flex flex-col gap-2', className)} aria-busy={loading || undefined}>
      <label
        htmlFor={controlId}
        className={cx(
          'type-body text-sm font-semibold',
          isDisabled ? 'text-text-disabled' : 'text-text-primary',
          labelHidden && 'sr-only',
        )}
      >
        {label}
      </label>
      {control}
      {hint && (
        <p id={hintId} className="type-supporting text-sm text-text-secondary">
          {hint}
        </p>
      )}
      {hasError && (
        <p
          id={errorId}
          role={announceError ? 'alert' : undefined}
          className="type-supporting text-sm text-danger"
        >
          {error}
        </p>
      )}
    </div>
  )
}
