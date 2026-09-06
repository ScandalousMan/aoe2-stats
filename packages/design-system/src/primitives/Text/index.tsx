import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/structural-tier.md §8 (T545, FR-020, FR-007).
// "Text owns every typography role, and the role-to-element mapping, so a caller never writes a
// font utility directly" (contracts/005-design-system-foundations/structural-tier.md). One
// element, carrying one named role from `tokens/font.json`'s `role` group — no wrapper, no icon
// slot, no decoration.

/** The six roles `font.json`'s `role` group names (contracts/token-families.md §4). One meaning
 * per role — `numeric`, `machine` and `identifier` used to share one monospace treatment for three
 * different meanings, and splitting them is what made digit alignment survive a font change
 * (research D7, SC-009). */
export type TextRole = 'display' | 'body' | 'supporting' | 'numeric' | 'machine' | 'identifier'

// §8's table names exactly one default element per role. Every row's own text is the sanctioned
// set for that role except `display`'s: "the level comes from `Page`/`Section`, not here" is the
// one sentence in the spec naming more than one legal element for a role, so `display` alone
// widens to every heading level and the other five stay singletons — a caller cannot render
// `body` as anything but a `<p>` through this primitive, which is exactly "never outside it".
interface TextElementsByRole {
  display: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
  body: 'p'
  supporting: 'p'
  numeric: 'span'
  machine: 'span'
  identifier: 'span'
}

export type TextProps<TRole extends TextRole = TextRole> = {
  role: TRole
  /** Overrides the element within the role's own sanctioned set (above) and never outside it — a
   * heading level for `display`, a no-op for every other role, whose set has exactly one member.
   * The role-to-element mapping stays a system decision either way (FR-020). */
  as?: TextElementsByRole[TRole]
  children?: ReactNode
} & Omit<HTMLAttributes<HTMLElement>, 'children' | 'className' | 'color' | 'role'>

interface RoleConfig<TRole extends TextRole> {
  element: TextElementsByRole[TRole]
  classes: string
}

// `tracking-tight` applies to `display` unconditionally: its one default size (`text-2xl`) is
// already inside "text-2xl and above only" (§8's tokens-used line), and this role has no smaller
// size to fall below that floor. `identifier` carries no separate colour class: `type-identifier`
// (font.json role group) already sets `color: text-secondary` in the utility itself — "identifier
// carries text-secondary by contract" (§8) — a second, later colour class here would only risk
// fighting it on source order for no benefit.
const roleConfig: { [K in TextRole]: RoleConfig<K> } = {
  display: {
    element: 'h2',
    classes: 'type-display text-2xl font-semibold tracking-tight text-text-primary',
  },
  body: { element: 'p', classes: 'type-body text-md font-normal text-text-primary' },
  supporting: { element: 'p', classes: 'type-supporting text-sm font-normal text-text-primary' },
  numeric: { element: 'span', classes: 'type-numeric text-md font-normal text-text-primary' },
  machine: { element: 'span', classes: 'type-machine text-sm font-normal text-text-primary' },
  identifier: { element: 'span', classes: 'type-identifier text-sm font-normal' },
}

// §8 "focus-visible": "`Text` is not focusable; a heading that receives programmatic focus (a
// `Callout`'s heading, a route-change announcement) takes `tabIndex={-1}` from its caller and
// shows the standard ring against the surface it sits on." The ring utilities cost nothing when
// the element never receives focus — `:focus-visible` never matches an element with no tab stop —
// so they are always present rather than conditioned on a `tabIndex` prop this component would
// otherwise have to inspect.
const focusRing =
  'outline-none focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

export function Text<TRole extends TextRole>({ role, as, children, ...rest }: TextProps<TRole>) {
  // §8 "empty": "`Text` with no children renders nothing, not an element occupying a line box."
  if (children === undefined || children === null || children === '') return null

  const config = roleConfig[role]
  const Tag = (as ?? config.element) as ElementType

  return (
    <Tag className={cx(config.classes, focusRing)} {...rest}>
      {children}
    </Tag>
  )
}
