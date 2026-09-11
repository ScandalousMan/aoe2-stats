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
// Remediation (fifth-pass review M2, corrected sixth-pass): `secondary` and `destructive` used to
// stop at the fill swap above — the same two-rung `surface-sunken`/`background` step `ghost` also
// takes, but with no shape change riding alongside it the way `ghost`'s `active:border-border-strong`
// gives that variant. Both already carry a *painted* border at rest (`border-border-strong` /
// `border-danger`), unlike `ghost` (`border-transparent` at rest) or the row components
// (`Menu`/`Table`/`MatchRow`/`PlayerResultRow`/`FavouritesList`, each `border-l-2 border-l-transparent`
// at rest) — there is no already-transparent rung here to swap paint into, so the reserve-then-paint
// border technique those components use does not transfer unmodified.
//
// The fifth-pass fix reached for `active:outline-2 active:outline-offset-0`, reasoning that `outline`
// cannot reflow. That reasoning was correct and the conclusion was wrong: `outline` never painted
// here at all. Every variant's focus ring above composes `outline-none`
// (`.outline-none{--tw-outline-style:none}`), and `tailwind.css`'s T096 fix restores that property
// only under `:focus-visible` — `:active` (or any other pseudo-class) leaves it `none` forever, and
// `outline-2`/`outline-offset-*` only *read* `--tw-outline-style`, they never set it. So
// `active:outline-2` compiled to a real CSS rule that resolves to `outline-style: none` at runtime:
// dead CSS, for exactly the reason T096's own comment documents, one pseudo-class over from the case
// it names. **The trap, for the next person**: an `outline` utility on any state other than
// `:focus-visible` is dead weight on any element composing `outline-none`, full stop — grep
// `active:outline`/`hover:outline` before adding one, and do not trust "it compiled" as evidence it
// paints.
//
// Sixth-pass fix: `active:ring-2 active:ring-<token>` — Tailwind's box-shadow-backed `ring` utility,
// which reads and writes only its own `--tw-ring-*` custom properties and never touches
// `--tw-outline-style`, so it cannot fall into the trap above. `box-shadow` never participates in
// layout, the same property `outline` was chosen for, so this keeps the original reflow-free
// requirement while actually painting — compiled with tailwindcss 4.3.3, `.active\:ring-2:active`
// emits `--tw-ring-shadow: var(--tw-ring-inset,) 0 0 0 calc(2px + var(--tw-ring-offset-width))
// var(--tw-ring-color, currentcolor)` composed into a real `box-shadow` declaration, and with
// `--tw-ring-offset-width` at its 0px default the shadow sits flush against the existing 1px border
// — the same seam the dead `outline-offset-0` was aiming for. Because `ring` paints through
// `box-shadow` and the focus ring above paints through `outline` — two different CSS properties —
// a keyboard `Enter` press (`:active` and `:focus-visible` matching at once) now genuinely shows
// both at the same time, which two rules fighting over the same `outline` property never could.
const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-accent-contrast hover:bg-accent-hover active:bg-accent-active border border-transparent',
  secondary:
    'bg-surface text-text-primary border border-border-strong hover:bg-surface-sunken active:bg-background active:ring-2 active:ring-border-strong',
  ghost:
    'bg-transparent text-text-primary border border-transparent hover:bg-surface-sunken active:bg-background active:border-border-strong',
  destructive:
    'bg-surface text-danger border border-danger hover:bg-surface-sunken active:bg-background active:ring-2 active:ring-danger',
}

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring'

// `primary` cannot ring with `focus-ring`: the ring must clear 3:1 against both `surface-raised`
// and `accent` (its own fill) at once, and no single colour can bridge a near-white page and a
// near-ink fill (proof in packages/design-system/specs/color-tokens.md §5, DS-10). So `primary`
// rings inward instead, in `accent-contrast` — the ink it already carries, which clears 4.5:1 on
// `accent`, `accent-hover` and `accent-active` alike (build-tokens.test.mjs).
//
// T586: `-outline-offset-2` on a 2px-wide ring paints exactly the outermost two pixels of the
// border box — flush with the edge, so the ring's outer side sat on the page (1.00-1.42:1, the
// same invisible-on-the-page defect §5 exists to prevent, in a new direction). `-outline-offset-4`
// moves the ring's inner edge 4px in, leaving a 2px band of `accent` fill (offset magnitude minus
// the 2px width) between the ring and the edge on every side, so both of its adjacent colours
// really are the fill. Checked against `md`, this variant's smallest rendered size (`h-10 px-4
// text-sm`): the ring's inner edge sits 4px inside the border box, far short of the 16px
// horizontal padding around the label, so it never comes near the text. Guarded by
// tokens/accent-contrast-ring.test.mjs, since no contrast test can see this — the pair it draws
// clears 3:1 regardless of where the ring sits.
const primaryFocusRing =
  'outline-none focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-accent-contrast'

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
