import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReactNode } from 'react'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'

// T563 (FR-040, FR-041). The reuse test in the `design-system` skill — "does an existing token
// already satisfy this need?" — has to be answerable here, before a component is written, so this
// page is the interactive form of two prose sources rather than a copy of either: the surface,
// ink and chromatic ramps (`specs/color-tokens.md` §3, §6, §11), and the measured pairs
// (`specs/README.md`, "Measured contrast pairs"). Every swatch below reads the real token through
// the same utility class a component would write, in whichever theme the toolbar has selected, so
// a stale value here is a rendering defect the visual suite would catch, not a paragraph nobody
// re-reads. **What this page deliberately does not do**: restate a contrast ratio as a number. The
// repository's own filing rule is that a measurement written twice goes stale in one copy, and
// `specs/README.md` already carries the asserted numbers (`build-tokens.test.mjs` re-asserts them
// on every change to `color.json`) — this page instead renders every declared pairing so a reader
// can *see* it hold, and links back to the measured table for the exact figure.

// Every Tailwind class this file paints is written out here as a literal (never composed with
// `` `bg-${role}` ``): Tailwind's scanner reads source text, not a runtime value, and a class
// built by interpolation compiles to nothing — the same reason `packages/design-system/src/
// primitives/Page/index.tsx`'s `widthClasses` record is a lookup table of literals rather than a
// template string.

const PAGE_SURFACES = [
  { key: 'surface-sunken', bg: 'bg-surface-sunken', label: 'surface-sunken' },
  { key: 'background', bg: 'bg-background', label: 'background' },
  { key: 'surface', bg: 'bg-surface', label: 'surface' },
  { key: 'surface-raised', bg: 'bg-surface-raised', label: 'surface-raised' },
] as const

type SurfaceKey = (typeof PAGE_SURFACES)[number]['key']

function findSurface(key: SurfaceKey) {
  const surface = PAGE_SURFACES.find((candidate) => candidate.key === key)
  if (!surface) throw new Error(`Foundations/Colour: "${key}" is not a declared page surface`)
  return surface
}

const chipShell =
  'flex h-16 w-32 shrink-0 flex-col items-center justify-center gap-1 rounded-panel p-2 text-center'

// specs/color-tokens.md §3.1 — the surface ramp, sunken to raised, one lift in both themes.
const SURFACE_RAMP = [
  {
    name: 'surface-sunken',
    bg: 'bg-surface-sunken',
    meaning: 'Recessed — well, track, disabled fill, hover row.',
  },
  { name: 'background', bg: 'bg-background', meaning: 'The page itself.' },
  { name: 'surface', bg: 'bg-surface', meaning: 'The default bounded surface — card, row, input.' },
  {
    name: 'surface-raised',
    bg: 'bg-surface-raised',
    meaning: 'Lifted off the page — panel, callout, menu, tooltip.',
  },
] as const

// specs/color-tokens.md §6 ("Role → declared surfaces") and §11.5 for the three link rows.
// `roleClass` paints the role as ink; `surfaces` is the declared list, always valid in both
// themes — a role a component paints on a surface not listed here is a defect regardless of
// whether the resulting pair happens to pass contrast (FR-005).
const INK_ROLES: {
  name: string
  roleClass: string
  meaning: string
  surfaces: SurfaceKey[]
  note?: string
  // Set only for a role the token ramp *deliberately* holds under 4.5:1 (color-tokens.md's own
  // "exempt" entries — today just `text-disabled`, WCAG 1.4.3's carve-out for text that is part of
  // an *inactive* interface component). `aria-hidden` was tried first and rejected: axe's
  // `color-contrast` check is a visual-rendering rule, not an accessibility-tree one — it still
  // flags an `aria-hidden` span exactly as it would any other visually-painted text, and rightly
  // so, since a low-vision reader with no assistive technology at all still looks straight at the
  // pixels. `aria-disabled="true"` is what axe's own check actually special-cases (mirroring the
  // WCAG carve-out itself: literally "part of an inactive interface component"), and it is also
  // the more honest label — the specimen word *is* what a disabled control's caption looks like,
  // which `role.meaning` already says in words, so a screen reader still gets the word plus its
  // disabled state rather than losing the node outright. A role that fails contrast by *mistake*
  // must never set this: it would suppress axe without fixing the token, which is not a
  // remediation, only a hidden regression.
  lowContrast?: boolean
}[] = [
  {
    name: 'text-primary',
    roleClass: 'text-text-primary',
    meaning: "The reader's primary text.",
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'text-secondary',
    roleClass: 'text-text-secondary',
    meaning: 'Supporting and explanatory text.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'text-disabled',
    roleClass: 'text-text-disabled',
    meaning: 'The label of an inactive control.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    note: 'Exempt from WCAG 1.4.3 (inactive), held to 3:1 anyway — a disabled control is often the one carrying the explanation.',
    lowContrast: true,
  },
  {
    name: 'link',
    roleClass: 'text-link underline',
    meaning: 'This text navigates.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    note: 'A distinct role from accent, deliberately: accent is the product\'s own emphasis, link means "this navigates", and the two must be able to move without dragging each other. The underline is structural, not decorative — a link is never colour alone.',
  },
  {
    name: 'link-hover',
    roleClass: 'text-link-hover underline',
    meaning: 'That link, hovered.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'link-visited',
    roleClass: 'text-link-visited underline',
    meaning: 'That link, already followed.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    note: 'A chroma cut, not a lightness step, so "spent" means the same thing in both themes. Browsers refuse to let Playwright or Storybook force real `:visited` styling, so this swatch — painting the token directly — is the visual acceptance criterion (color-tokens.md §11.7), not a screenshot of a real anchor.',
  },
]

// specs/color-tokens.md §6 — `border` and `border-strong` are never painted as ink in any
// shipping component (their real call sites are all boundaries), and `focus-ring` is painted as
// an outline, never as text colour — so all three are demonstrated only in their real shape,
// below, rather than invented as an ink pairing nothing actually draws.

const BOUNDARY_ROLES: {
  name: string
  borderClass: string
  meaning: string
  surfaces: SurfaceKey[]
}[] = [
  {
    name: 'border',
    borderClass: 'border-border',
    meaning: 'A decorative separator or an inactive boundary — a table row rule, a footer rule.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'border-strong',
    borderClass: 'border-border-strong',
    meaning: 'The boundary of an interactive control or a mark — a Button, a swatch frame.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
]

// The fill roles: `swatchClass` paints the fill, `contrastClass` paints its own ink on top, and
// `surfaces` is the page background the swatch is placed on to demonstrate the pairing (never a
// surface the fill itself resolves to).
const FILL_ROLES: {
  name: string
  swatchClass: string
  contrastClass: string | null
  meaning: string
  surfaces: SurfaceKey[]
  note?: string
}[] = [
  {
    name: 'accent',
    swatchClass: 'bg-accent',
    contrastClass: 'text-accent-contrast',
    meaning: "The product's emphasis, as fill or ink.",
    surfaces: ['background', 'surface', 'surface-raised'],
    note: 'Not surface-sunken: 4.27:1 there in light, under the 4.5 floor.',
  },
  {
    name: 'accent-hover',
    swatchClass: 'bg-accent-hover',
    contrastClass: 'text-accent-contrast',
    meaning: 'That emphasis, hovered.',
    surfaces: ['background', 'surface', 'surface-raised'],
  },
  {
    name: 'accent-active',
    swatchClass: 'bg-accent-active',
    contrastClass: 'text-accent-contrast',
    meaning: 'That emphasis, pressed.',
    surfaces: ['background', 'surface', 'surface-raised'],
  },
  {
    name: 'success',
    swatchClass: 'bg-success',
    contrastClass: 'text-success-contrast',
    meaning: 'A favourable outcome.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'warning',
    swatchClass: 'bg-warning',
    contrastClass: 'text-warning-contrast',
    meaning: 'A caution the reader should act on.',
    surfaces: ['surface-raised'],
    note: 'Callout and Badge are unconditionally surface-raised — the role declares only the surface a component actually paints it on.',
  },
  {
    name: 'danger',
    swatchClass: 'bg-danger',
    contrastClass: 'text-danger-contrast',
    meaning: 'A destructive action or an unfavourable outcome.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
  },
  {
    name: 'info',
    swatchClass: 'bg-info',
    contrastClass: 'text-info-contrast',
    meaning: 'A neutral statement of fact.',
    surfaces: ['surface-raised'],
  },
]

const PLAYER_COLOURS = [
  { name: 'player-1', swatch: 'bg-player-1', ink: 'text-player-1-contrast', label: 'Blue' },
  { name: 'player-2', swatch: 'bg-player-2', ink: 'text-player-2-contrast', label: 'Red' },
  { name: 'player-3', swatch: 'bg-player-3', ink: 'text-player-3-contrast', label: 'Green' },
  { name: 'player-4', swatch: 'bg-player-4', ink: 'text-player-4-contrast', label: 'Yellow' },
  { name: 'player-5', swatch: 'bg-player-5', ink: 'text-player-5-contrast', label: 'Teal' },
  { name: 'player-6', swatch: 'bg-player-6', ink: 'text-player-6-contrast', label: 'Purple' },
  { name: 'player-7', swatch: 'bg-player-7', ink: 'text-player-7-contrast', label: 'Grey' },
  { name: 'player-8', swatch: 'bg-player-8', ink: 'text-player-8-contrast', label: 'Orange' },
] as const

function RoleName({ children }: { children: ReactNode }) {
  return (
    <code className="type-machine rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
      {children}
    </code>
  )
}

function InkRoleCard(role: (typeof INK_ROLES)[number]) {
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Text role="supporting">{role.meaning}</Text>
      </div>
      {role.note && <Text role="supporting">{role.note}</Text>}
      <div className="flex flex-wrap gap-3">
        {role.surfaces.map((key) => {
          const surface = findSurface(key)
          return (
            <div key={key} className={cx(chipShell, surface.bg)}>
              {/* `role.lowContrast` roles (today: text-disabled) are held under 4.5:1 by design
                  (color-tokens.md's own WCAG 1.4.3 exemption for text that is part of an inactive
                  interface component) — `aria-disabled` names exactly that state, which is also
                  what the specimen literally shows (role.meaning: "the label of an inactive
                  control"), and it is the attribute axe's own `color-contrast` check special-cases
                  for this reason, rather than flagging visually-painted text no assistive
                  technology is even involved in reading (both themes). A role that is *not*
                  declared `lowContrast` renders this span exactly as before: real, readable,
                  non-exempt text. */}
              <span
                className={cx('type-body text-sm', role.roleClass)}
                aria-disabled={role.lowContrast || undefined}
              >
                Text
              </span>
              <span className="type-identifier text-xs">{surface.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function BoundaryRoleCard(role: (typeof BOUNDARY_ROLES)[number]) {
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Text role="supporting">{role.meaning}</Text>
      </div>
      <div className="flex flex-wrap gap-3">
        {role.surfaces.map((key) => {
          const surface = findSurface(key)
          return (
            <div
              key={key}
              className={cx(chipShell, surface.bg, 'border-hairline', role.borderClass)}
            >
              <span className="type-identifier text-xs">{surface.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FillRoleCard(role: (typeof FILL_ROLES)[number]) {
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Text role="supporting">{role.meaning}</Text>
      </div>
      {role.note && <Text role="supporting">{role.note}</Text>}
      <div className="flex flex-wrap gap-3">
        {role.surfaces.map((key) => {
          const surface = findSurface(key)
          return (
            <div key={key} className={cx('rounded-panel p-3', surface.bg)}>
              <div
                className={cx(
                  'flex h-12 w-24 items-center justify-center rounded-control text-xs',
                  role.swatchClass,
                  role.contrastClass,
                )}
              >
                {role.name}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const meta: Meta = {
  title: 'Foundations/Colour',
  parameters: {
    layout: 'fullscreen',
  },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Colour"
        description="Every semantic role, what it means, the surfaces it may be painted on, and its declared pairs. Numbers live in specs/README.md and specs/color-tokens.md; this page shows the pairing itself."
      >
        <Section heading="Surfaces">
          <div className="flex flex-wrap gap-3">
            {SURFACE_RAMP.map((surface) => (
              <div
                key={surface.name}
                className={cx(
                  'flex h-24 w-40 flex-col items-start justify-end gap-1 rounded-panel border-hairline border-border p-3',
                  surface.bg,
                )}
              >
                <RoleName>{surface.name}</RoleName>
                <span className="type-supporting text-xs text-text-secondary">
                  {surface.meaning}
                </span>
              </div>
            ))}
          </div>
        </Section>

        <Section heading="Text and lines">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {INK_ROLES.map((role) => (
              <InkRoleCard key={role.name} {...role} />
            ))}
          </div>
        </Section>

        <Section heading="Boundaries, painted as a border">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {BOUNDARY_ROLES.map((role) => (
              <BoundaryRoleCard key={role.name} {...role} />
            ))}
          </div>
        </Section>

        <Section heading="Focus ring, painted as a ring">
          <div className="flex flex-wrap gap-3">
            {PAGE_SURFACES.map((surface) => (
              <div
                key={surface.key}
                className={cx(
                  chipShell,
                  surface.bg,
                  'outline outline-ring outline-offset-ring outline-focus-ring',
                )}
              >
                <span className="type-identifier text-xs">{surface.label}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section heading="Emphasis and status">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {FILL_ROLES.map((role) => (
              <FillRoleCard key={role.name} {...role} />
            ))}
          </div>
        </Section>

        <Section
          heading="Overlay"
          description="A scrim that removes the page beneath a modal — Dialog's backdrop, Menu's mobile backdrop. Carries no foreground: nothing is read against a scrim."
        >
          <div className="relative h-32 w-64 overflow-hidden rounded-panel border-hairline border-border">
            <div className="flex h-full items-center justify-center bg-surface">
              <span className="type-body text-sm text-text-primary">Page content</span>
            </div>
            <div className="absolute inset-0 flex items-center justify-center bg-overlay">
              {/* The scrim itself carries no ink (README: "nothing is read against a scrim") —
                  what reads is the dialog's own surface-raised panel sitting on top of it, exactly
                  as Dialog composes it, never text painted on the overlay fill directly. */}
              <div className="rounded-panel bg-surface-raised px-3 py-2 shadow-modal">
                <span className="type-body text-sm text-text-primary">Dialog above</span>
              </div>
            </div>
          </div>
        </Section>

        <Section
          heading="Player colours"
          description="A player's own colour, theme-invariant — the fill and its ink carry one value in both themes because a player's colour is their identity, not a mood. Framed in border-strong, per player-colour-swatch.md."
        >
          <div className="flex flex-wrap gap-3">
            {PLAYER_COLOURS.map((player) => (
              <div
                key={player.name}
                className={cx(
                  'flex h-16 w-20 flex-col items-center justify-center gap-1 rounded-control border-hairline border-border-strong text-xs',
                  player.swatch,
                  player.ink,
                )}
              >
                <span>{player.label}</span>
              </div>
            ))}
          </div>
        </Section>
      </Section>
    </div>
  ),
}
