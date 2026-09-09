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
//
// `secondary` / `ghost` / `destructive` step through the surface ramp's two attenuated rungs
// rather than one repeated twice (third-pass review remediation, FR-037): hover deepens to
// `surface-sunken`, the ramp's darkest surface, and active moves to `background`, the ramp's
// other attenuated step — a different, already-measured token (README's contrast table:
// `text-primary`/`danger` on `background` and on `surface-sunken` are both asserted), so pressing
// renders visibly differently from hovering rather than repainting the same pixels. `background`
// cannot be used for *hover* instead — several ghost buttons render directly on a `bg-background` page
// (`Page`'s `actions` slot, e.g. `DashboardContainer`'s "Search players" / "Sign out") and `ghost`
// carries no boundary until `active`, so a `background`-filled hover would be invisible there;
// `surface-sunken` never is, because it is darker than every surface it can sit on. `ghost` also
// gains its `border-strong` boundary only at `active`, never at `hover`, so pressing adds a shape
// signal on top of the fill change. `secondary` keeps its `border-strong` boundary at every state
// (rest already declares it, so repeating it at `active` was dead weight — removed); `destructive`
// keeps `border-danger` at every state instead of the neutral `border-strong` it used to swap to
// on press, so a pressed destructive button never reads as merely neutral.
// Remediation (fifth-pass review M2): `secondary` and `destructive` used to stop at the fill swap
// above — the same two-rung `surface-sunken`/`background` step `ghost` also takes, but with no
// shape change riding alongside it the way `ghost`'s `active:border-border-strong` gives that
// variant. `quickstart.md`'s own standard ("a non-colour signal … rather than a second fill, which
// is what the requirement's 'more than colour' actually asks") was applied to `ghost` and left
// unapplied one line away in the same object literal. Both already carry a border at rest, so
// `ghost`'s technique (transparent-to-painted) does not fit unmodified — an `outline`, not a border-
// width change, is what `active:outline-2 active:outline-offset-0` gives them instead: flush against
// the existing 1px border, in the same neutral token that border already carries (`border-strong` /
// `danger`), reading as the frame thickening on press. `outline` never participates in layout (the
// same property the focus ring above already rides, precisely because it cannot reflow), so this is
// safe at every width without the reservation dance `border` would need — verified: `outline-2`'s
// own width is added only while `active:` matches, and an outline never changes a box's rendered
// size or its neighbours' position, unlike a border-width change would on a box with no spare
// padding to absorb it.
const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-accent-contrast hover:bg-accent-hover active:bg-accent-active border border-transparent',
  secondary:
    'bg-surface text-text-primary border border-border-strong hover:bg-surface-sunken active:bg-background active:outline-2 active:outline-offset-0 active:outline-border-strong',
  ghost:
    'bg-transparent text-text-primary border border-transparent hover:bg-surface-sunken active:bg-background active:border-border-strong',
  destructive:
    'bg-surface text-danger border border-danger hover:bg-surface-sunken active:bg-background active:outline-2 active:outline-offset-0 active:outline-danger',
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
