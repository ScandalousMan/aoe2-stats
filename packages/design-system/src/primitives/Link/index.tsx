import type { AnchorHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §9 (T545, FR-006, FR-020).
// "Link owns the link roles from T522, the permanent underline and external-link semantics, so a
// caller never colours a link by hand" (contracts/005-design-system-foundations/structural-tier.md).
// A real `<a href>` — never a div, never a button that navigates (§9 Anatomy).

export type LinkVariant = 'inline' | 'standalone'

// `className` is deliberately excluded: `{...rest}` spreads after the computed `className` below,
// so accepting one here would let a caller silently replace every class this primitive owns — the
// exact "colour a link by hand" escape the contract forbids (same reasoning as `Page`'s own
// omission).
export interface LinkProps extends Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  'children' | 'href' | 'target' | 'rel' | 'className'
> {
  href: string
  /** `inline` (default): a link inside running prose, inheriting the surrounding role and size.
   * `standalone`: a navigation or action link on its own line, `type-body` at `text-md`, with a
   * 44px minimum hit area. `external` is not a third variant (§9): it is a fact about the
   * destination, layered onto either. */
  variant?: LinkVariant
  /** Marks the link's destination as leaving the product. Adds the drawn external mark after the
   * label, a visually hidden "(opens in a new tab)", and opens in a new tab
   * (`target="_blank" rel="noopener noreferrer"`) — the reader is never sent to a third-party site
   * without warning and without a way back to this tab. */
  external?: boolean
  children: ReactNode
}

// Ink: `link` at rest, `link-hover` on hover *and* on `:active` — a keyboard `Enter` triggers
// `:active` with no pointer ever hovering, and "active … inline: the hover paint" (§9) requires the
// hover paint to reach that path too, not only the mouse one. `visited:link-visited` cannot be
// observed in a real render (browsers restrict `:visited` styling), so its only proof is the
// token-swatch story (§9 "Visited").
const ink = 'text-link hover:text-link-hover active:text-link-hover visited:text-link-visited'

// Underline: `border.hairline` (1px) at rest, thickening to `border.ring` (2px) on hover/active —
// "two signals, one of which is not colour" (§9, FR-037). `decoration-1`/`decoration-2` are bare
// Tailwind numbers rather than a bracketed literal (`decoration-[2px]` fails token-scale.mjs),
// reached the same way `tokens/motion.json`'s own $comment already reaches `duration-120`: "the
// closed set a component picks from" is expressed as the nearest bare Tailwind utility because no
// `border.json` utility maps `ring`/`hairline` onto decoration-thickness (only onto border-width
// and outline-width, contracts/token-families.md §2). The values are not invented — they are
// `border.hairline` and `border.ring`, reached without a token-scale-forbidden literal. Colour
// transitions (`transition-colors`) at `motion.duration.fast`; the thickness switch is *not*
// covered by `transition-colors` and so is instant on its own, matching "the thickness switches
// instantly, because an animating underline is motion carrying a state change" (§9) with no extra
// class needed.
const underline = 'underline decoration-1 underline-offset-2 hover:decoration-2 active:decoration-2'

const transition = 'transition-colors duration-120 ease-standard motion-reduce:duration-0'

// `outline-ring` / `outline-offset-ring` / `focus-ring` — the same ring `Page` (T543) already
// draws, around the whole link box, on top of whatever the hover paint is (§9 "focus-visible").
const focusRing =
  'outline-none focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

// `standalone`'s own press feedback: `surface-sunken` behind the link's box, `rounded-control` —
// "nav links" is one of `radius.json`'s own named `control`-role call sites. `inline` gets no fill
// at all: "painting a wash behind three words inside a paragraph breaks the line and the press is a
// frame the reader never sees" (§9 "active").
const variantClasses: Record<LinkVariant, string> = {
  inline: '',
  standalone:
    'inline-flex items-center gap-2 rounded-control py-3 type-body text-md active:bg-surface-sunken',
}

// `inline`'s own wrapper, added only when `external` also adds a mark that must never strand on
// its own line (§9's external-link visual acceptance criterion): "An inline link adds no spacing
// at all: it is a run of text inside a line" (§9 "Responsive") stays true for a plain inline link,
// which never receives this class.
const externalInlineWrapper = 'inline-flex items-baseline gap-1'

/** The drawn external-link mark (§9 Anatomy): an inline path from `currentColor`, `aria-hidden`,
 * beside the visually hidden "(opens in a new tab)" text that is the link's real accessible
 * signal. Not an asset — the structural tier renders none (structural-tier.md's own header). */
function ExternalMark() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 16 16"
      className="icon-xs shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 4h6v6" />
      <path d="M12 4 4 12" />
    </svg>
  )
}

export function Link({ href, variant = 'inline', external = false, children, ...rest }: LinkProps) {
  // §9 "empty": "A `Link` with no text renders nothing." An icon-only link is forbidden in this
  // tier (README's iconography contract) — the mark is never the thing that is named.
  if (children === undefined || children === null || children === '') return null

  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      className={cx(
        ink,
        underline,
        transition,
        focusRing,
        variantClasses[variant],
        variant === 'inline' && external && externalInlineWrapper,
      )}
      {...rest}
    >
      {children}
      {external && (
        <>
          <ExternalMark />
          <span className="sr-only">(opens in a new tab)</span>
        </>
      )}
    </a>
  )
}
