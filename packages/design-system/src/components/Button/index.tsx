import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Spinner } from '../../lib/Spinner'

// packages/design-system/specs/shared-primitives.md#Button

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type ButtonSize = 'md' | 'lg'

interface SharedProps {
  variant?: ButtonVariant
  /** `md` is pointer-only (spec, §Sizes). Any button reachable on a touch viewport must be `lg`. */
  size?: ButtonSize
  /** Present while the action triggered by this button is in flight. Replaces the leading icon
   * slot with a spinner and the label with a present-participle description; the button keeps its
   * resting width. */
  loading?: boolean
  /** Present-participle label shown while `loading` ("Taking you to Steam…"). A caller that omits
   * this while `loading` gets the original label plus the spinner, never a bare spinner. */
  loadingLabel?: string
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
  children: ReactNode
}

export type ButtonProps = SharedProps &
  (
    | ({ href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>)
    | ({ href: string } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'children' | 'href'>)
  )

const sizeClasses: Record<ButtonSize, string> = {
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-md',
}

// Resting, hover and active fills. `primary` rests on `accent` and darkens through `accent-hover`
// then `accent-active` in both themes — three deliberately distinct colours (T034a), never
// collapsed onto one another. `destructive` never fills with `danger`: there is no `danger-hover`
// or `danger-active` token and inventing one is forbidden, so its hover/active deepen the neutral
// fill instead and keep `danger` for label and boundary.
const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-accent-contrast hover:bg-accent-hover active:bg-accent-active border border-transparent',
  secondary:
    'bg-surface text-text-primary border border-border-strong hover:bg-surface-sunken active:bg-surface-sunken active:border-border-strong',
  ghost:
    'bg-transparent text-text-primary border border-transparent hover:bg-surface-sunken active:bg-surface-sunken active:border-border-strong',
  destructive:
    'bg-surface text-danger border border-danger hover:bg-surface-sunken active:bg-surface-sunken active:border-border-strong',
}

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring'

// `primary` cannot ring with `focus-ring`: the ring must clear 3:1 against both `surface-raised`
// and `accent` (its own fill) at once, and no single colour can bridge a near-white page and a
// near-ink fill (proof in packages/design-system/specs/color-tokens.md §5, DS-10). So `primary`
// rings inward instead, in `accent-contrast` — the ink it already carries, which clears 4.5:1 on
// `accent`, `accent-hover` and `accent-active` alike (build-tokens.test.mjs).
const primaryFocusRing =
  'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-contrast'

const base = cx(
  'inline-flex items-center justify-center gap-2 rounded-control font-sans font-semibold',
  'transition-colors duration-120 ease-standard motion-reduce:duration-0',
  'disabled:bg-surface-sunken disabled:text-text-disabled disabled:border-border disabled:cursor-default',
)

export function Button(props: ButtonProps) {
  const {
    variant = 'secondary',
    size = 'md',
    loading = false,
    loadingLabel,
    leadingIcon,
    trailingIcon,
    children,
    className,
    href,
    ...rest
  } = props as ButtonProps & { className?: string }

  const label = loading ? (loadingLabel ?? children) : children
  const leading = loading ? <Spinner /> : leadingIcon

  const content = (
    <>
      {leading && <span className="inline-flex shrink-0 items-center">{leading}</span>}
      <span>{label}</span>
      {!loading && trailingIcon && (
        <span className="inline-flex shrink-0 items-center">{trailingIcon}</span>
      )}
    </>
  )

  const classes = cx(
    base,
    sizeClasses[size],
    variantClasses[variant],
    variant === 'primary' ? primaryFocusRing : focusRing,
    className,
  )

  if (href !== undefined) {
    return (
      <a
        href={href}
        className={classes}
        aria-busy={loading || undefined}
        {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}
      >
        {content}
      </a>
    )
  }

  const {
    type = 'button',
    disabled,
    ...buttonRest
  } = rest as ButtonHTMLAttributes<HTMLButtonElement>

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...buttonRest}
    >
      {content}
    </button>
  )
}
