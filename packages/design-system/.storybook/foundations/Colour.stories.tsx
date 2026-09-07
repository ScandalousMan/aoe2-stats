import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReactNode } from 'react'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import color from '../../tokens/color.json'

// T572 remediation (scenario 9). The reuse test in the `design-system` skill — "does an existing
// token already satisfy this need?" — has to be answerable here, before a component is written,
// so this page is the interactive form of two prose sources rather than a copy of either: the
// surface, ink and chromatic ramps (`specs/color-tokens.md` §3, §6, §11), and the measured pairs
// (`specs/README.md`, "Measured contrast pairs"). Every swatch below reads the real token through
// the same utility class a component would write, in whichever theme the toolbar has selected, so
// a stale value here is a rendering defect the visual suite would catch, not a paragraph nobody
// re-reads.
//
// **What changed in the T572 remediation.** The previous revision of this page painted every
// pairing but never printed a number: a reader with the built Storybook and no repository access
// could see that `danger` is legible on `surface-raised` but could not learn its hex value or its
// measured ratio without opening `specs/color-tokens.md` or `specs/README.md`, neither of which
// ships in the static build. Every hex below is read from `tokens/color.json` — the same import
// `build-tokens.mjs` reads to generate the CSS this page's own utility classes resolve to — for
// whichever theme the toolbar has selected, so a value here cannot go stale independently of the
// token it names. Every contrast ratio is *computed*, live, from that pair of hexes, with the same
// WCAG 2.2 relative-luminance formula `tokens/build-tokens.test.mjs` already asserts against — a
// derivation of the generated token, not a second transcription of `README.md`'s table, so an edit
// to `color.json` changes the number this page shows on its very next render. `specs/README.md`
// and `specs/color-tokens.md` are still cited, in addition, for the reasoning behind a value; the
// value itself no longer requires opening either file.
//
// Every Tailwind class this file paints is written out here as a literal (never composed with
// `` `bg-${role}` ``): Tailwind's scanner reads source text, not a runtime value, and a class
// built by interpolation compiles to nothing — the same reason `packages/design-system/src/
// primitives/Page/index.tsx`'s `widthClasses` record is a lookup table of literals rather than a
// template string.

type Palette = (typeof color)['light']
type ColorRoleKey = keyof Palette

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

// --- Contrast, derived live -----------------------------------------------------------------
// The same WCAG 2.2 relative-luminance formula `tokens/build-tokens.test.mjs` computes the
// measured-pairs table with, reproduced here so this page can answer "is this pair legible?" from
// the two token values it is already painting, rather than sending the reader to
// `specs/README.md`'s table for the number. This is a derivation of the generated token, not a
// second copy of a measurement: nothing here is hand-typed, and an edit to `color.json` changes
// what every ratio below reads on its next render.
function srgbToLinear(channel: number) {
  const c = channel / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function relativeLuminance(hex: string) {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16))
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

function contrastRatio(hexA: string, hexB: string) {
  const lA = relativeLuminance(hexA)
  const lB = relativeLuminance(hexB)
  const lighter = Math.max(lA, lB)
  const darker = Math.min(lA, lB)
  return (lighter + 0.05) / (darker + 0.05)
}

function formatRatio(hexA: string, hexB: string) {
  return `${contrastRatio(hexA, hexB).toFixed(2)}:1`
}

function Hex({ children }: { children: string }) {
  return <code className="type-machine text-xs text-text-secondary">{children}</code>
}

// Three-line tiles: role/surface identity, the surface's own hex, and the ratio the pair measures
// — one line more than the two-line tile this page shipped with, and the direct answer to "which
// colour is this, and is it legible here" without leaving the page.
const chipShell =
  'flex h-20 w-32 shrink-0 flex-col items-center justify-center gap-1 rounded-panel p-2 text-center'

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
// whether the resulting pair happens to pass contrast (FR-005). `floor` is the accessibility
// obligation this pairing owes (README, "Thresholds"): 4.5 for normal text, 3 for a role this
// page's own ramp holds to the non-text floor by design.
const INK_ROLES: {
  name: ColorRoleKey
  roleClass: string
  meaning: string
  surfaces: SurfaceKey[]
  floor: number
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
    floor: 4.5,
  },
  {
    name: 'text-secondary',
    roleClass: 'text-text-secondary',
    meaning: 'Supporting and explanatory text.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    floor: 4.5,
  },
  {
    name: 'text-disabled',
    roleClass: 'text-text-disabled',
    meaning: 'The label of an inactive control.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    floor: 3,
    note: 'Exempt from WCAG 1.4.3 (inactive), held to 3:1 anyway — a disabled control is often the one carrying the explanation.',
    lowContrast: true,
  },
  {
    name: 'link',
    roleClass: 'text-link underline',
    meaning: 'This text navigates.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    floor: 4.5,
    note: 'A distinct role from accent, deliberately: accent is the product\'s own emphasis, link means "this navigates", and the two must be able to move without dragging each other. The underline is structural, not decorative — a link is never colour alone.',
  },
  {
    name: 'link-hover',
    roleClass: 'text-link-hover underline',
    meaning: 'That link, hovered.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    floor: 4.5,
  },
  {
    name: 'link-visited',
    roleClass: 'text-link-visited underline',
    meaning: 'That link, already followed.',
    surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
    floor: 4.5,
    note: 'A chroma cut, not a lightness step, so "spent" means the same thing in both themes. Browsers refuse to let Playwright or Storybook force real `:visited` styling, so this swatch — painting the token directly — is the visual acceptance criterion (color-tokens.md §11.7), not a screenshot of a real anchor.',
  },
]

// specs/color-tokens.md §6 — `border` and `border-strong` are never painted as ink in any
// shipping component (their real call sites are all boundaries), and `focus-ring` is painted as
// an outline, never as text colour — so all three are demonstrated only in their real shape,
// below, rather than invented as an ink pairing nothing actually draws. Non-text boundary floor:
// 3:1 (WCAG 1.4.11).

const BOUNDARY_ROLES: {
  name: ColorRoleKey
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

// --- Emphasis and status ------------------------------------------------------------------------
// T572 remediation (defects 2 and 4). The previous revision showed every one of these seven roles
// as a single filled swatch, which is true of `accent`, `accent-hover` and `accent-active` but not
// of `success`, `warning`, `danger` or `info`: reading every real call site in
// `packages/design-system/src` (Callout, Badge, MatchRow, MatchDetailPanel, ProfileSummary,
// Button, ThirdPartyObjectionForm) finds `warning` and `info` painted only as ink and as a
// stripe-shaped border, never as a fill, and finds `success` and `danger` painted as ink, as a
// border *and* as a fill, on more surfaces than either shape shows alone. Showing every role as a
// filled swatch could not tell these apart; showing nothing but a filled swatch for `danger`
// contradicted the very rule this section states for `warning`. Below, a role renders only the
// shapes it is actually used in, each captioned with the real surfaces that shape paints on and
// each tile carrying the surface's hex and the pair's live contrast ratio — the same treatment
// "Text and lines" already gives an ink role, generalised to a role that may be more than one
// shape at once.
type StatusInk = { surfaces: SurfaceKey[]; roleClass: string; note: string }
type StatusBorder = { surfaces: SurfaceKey[]; borderClass: string; note: string }
type StatusFill = {
  demoSurface: SurfaceKey
  swatchClass: string
  contrastKey: ColorRoleKey | null
  contrastClass: string | null
  note: string
}

type StatusRoleDef = {
  name: ColorRoleKey
  meaning: string
  ink?: StatusInk
  border?: StatusBorder
  fill?: StatusFill
}

const STATUS_ROLES: StatusRoleDef[] = [
  {
    name: 'accent',
    meaning: "The product's emphasis, as a fill or as ink — never both for the same call site.",
    fill: {
      demoSurface: 'surface',
      swatchClass: 'bg-accent',
      contrastKey: 'accent-contrast',
      contrastClass: 'text-accent-contrast',
      note: "SiteHeader's current-tab underline, drawn on the header's own surface. Button's primary fill and DataExportPanel's download-link fill draw the same accent/accent-contrast pair on the control's own body, wherever that control sits on the page — the pairing does not depend on what surrounds it.",
    },
    ink: {
      surfaces: ['surface-raised'],
      roleClass: 'text-accent',
      note: "Badge's accent tone in the dark theme. The light theme paints the identical tone with accent-active instead (below): accent alone falls under 4.5:1 on surface-raised in light.",
    },
  },
  {
    name: 'accent-hover',
    meaning: 'That emphasis, hovered — a fill only; nothing pairs it with ink on a page surface.',
    fill: {
      demoSurface: 'surface',
      swatchClass: 'bg-accent-hover',
      contrastKey: 'accent-contrast',
      contrastClass: 'text-accent-contrast',
      note: "Button's hover fill and DataExportPanel's hover fill — always the control's own body, never a page surface.",
    },
  },
  {
    name: 'accent-active',
    meaning: 'That emphasis, pressed — a fill, and (light theme only) ink.',
    fill: {
      demoSurface: 'surface',
      swatchClass: 'bg-accent-active',
      contrastKey: 'accent-contrast',
      contrastClass: 'text-accent-contrast',
      note: "Button's active fill and DataExportPanel's active fill — the control's own body.",
    },
    ink: {
      surfaces: ['surface-raised'],
      roleClass: 'text-accent-active',
      note: "Badge's accent tone in the light theme (the dark theme uses accent itself, above).",
    },
  },
  {
    name: 'success',
    meaning: 'A favourable outcome, as ink, as a border or as a fill.',
    ink: {
      surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
      roleClass: 'text-success',
      note: "MatchRow's win text on surface, and on surface-sunken under a row hover; ProfileSummary's rating delta on background; Callout's heading and Badge's tone, both on surface-raised.",
    },
    border: {
      surfaces: ['surface-raised'],
      borderClass: 'border-success',
      note: "Callout's left stripe — Callout is unconditionally surface-raised, so this is its only surface.",
    },
    fill: {
      demoSurface: 'surface-sunken',
      swatchClass: 'bg-success',
      contrastKey: null,
      contrastClass: null,
      note: "ProfileSummary's win/loss record bar, filled directly over its own surface-sunken track. No ink is drawn on the bar itself — the percentage label beside it is what satisfies rule 4 (colour is never the only carrier of the fact).",
    },
  },
  {
    name: 'warning',
    meaning: 'A caution the reader should act on, as ink or as a border — never a fill.',
    ink: {
      surfaces: ['surface-raised'],
      roleClass: 'text-warning',
      note: 'Callout and Badge are its only consumers, and both are unconditionally surface-raised — the role declares only the surface a component actually paints it on.',
    },
    border: {
      surfaces: ['surface-raised'],
      borderClass: 'border-warning',
      note: "Callout's left stripe, the same unconditional surface.",
    },
  },
  {
    name: 'danger',
    meaning: 'A destructive action or an unfavourable outcome, as ink, as a border or as a fill.',
    ink: {
      surfaces: ['background', 'surface', 'surface-raised', 'surface-sunken'],
      roleClass: 'text-danger',
      note: "Wider than warning's single surface for the same rule, not an exception to it: MatchRow's loss text (surface, and surface-sunken under a row hover) and ProfileSummary's rating delta (background) paint danger directly on the page, alongside Callout's heading and Badge's tone on surface-raised.",
    },
    border: {
      surfaces: ['surface', 'surface-raised'],
      borderClass: 'border-danger',
      note: "Button's destructive variant and ThirdPartyObjectionForm's field error, both on the control's own surface; Callout's left stripe on surface-raised.",
    },
    fill: {
      demoSurface: 'surface-sunken',
      swatchClass: 'bg-danger',
      contrastKey: null,
      contrastClass: null,
      note: "ProfileSummary's win/loss record bar, filled directly over its own surface-sunken track — no ink, for the same reason as success, above.",
    },
  },
  {
    name: 'info',
    meaning: 'A neutral statement of fact, as ink or as a border — never a fill.',
    ink: {
      surfaces: ['surface-raised'],
      roleClass: 'text-info',
      note: 'Callout and Badge are its only consumers, and both are unconditionally surface-raised — the same rule warning obeys, above.',
    },
    border: {
      surfaces: ['surface-raised'],
      borderClass: 'border-info',
      note: "Callout's left stripe, the same unconditional surface.",
    },
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

function InkRoleCard(role: (typeof INK_ROLES)[number], palette: Palette) {
  const inkHex = palette[role.name]
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Hex>{inkHex}</Hex>
        <Text role="supporting">{role.meaning}</Text>
      </div>
      {role.note && <Text role="supporting">{role.note}</Text>}
      <div className="flex flex-wrap gap-3">
        {role.surfaces.map((key) => {
          const surface = findSurface(key)
          const surfaceHex = palette[key]
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
              <span className="type-identifier text-xs">
                {formatRatio(inkHex, surfaceHex)} · floor {role.floor}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function BoundaryRoleCard(role: (typeof BOUNDARY_ROLES)[number], palette: Palette) {
  const borderHex = palette[role.name]
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Hex>{borderHex}</Hex>
        <Text role="supporting">{role.meaning}</Text>
      </div>
      <div className="flex flex-wrap gap-3">
        {role.surfaces.map((key) => {
          const surface = findSurface(key)
          const surfaceHex = palette[key]
          return (
            <div
              key={key}
              className={cx(chipShell, surface.bg, 'border-hairline', role.borderClass)}
            >
              <span className="type-identifier text-xs">{surface.label}</span>
              <span className="type-identifier text-xs">
                {formatRatio(borderHex, surfaceHex)} · floor 3
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StatusRoleCard(role: StatusRoleDef, palette: Palette) {
  const { fill, ink, border } = role
  return (
    <div className="flex flex-col gap-4 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <RoleName>{role.name}</RoleName>
        <Text role="supporting">{role.meaning}</Text>
      </div>

      {fill && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="type-identifier text-xs">fill</span>
            <Hex>{palette[role.name]}</Hex>
            {fill.contrastKey && (
              <>
                <span className="type-identifier text-xs">on ink</span>
                <Hex>{palette[fill.contrastKey]}</Hex>
                <span className="type-identifier text-xs">
                  {formatRatio(palette[fill.contrastKey], palette[role.name])} · floor 4.5
                </span>
              </>
            )}
          </div>
          <div
            className={cx(
              'flex w-fit flex-col items-center gap-1 rounded-panel p-3',
              findSurface(fill.demoSurface).bg,
            )}
          >
            <div
              className={cx(
                'flex h-12 w-24 items-center justify-center rounded-control text-xs',
                fill.swatchClass,
                fill.contrastClass,
              )}
            >
              {fill.contrastClass ? role.name : null}
            </div>
            <span className="type-identifier text-xs">{findSurface(fill.demoSurface).label}</span>
          </div>
          <Text role="supporting">{fill.note}</Text>
        </div>
      )}

      {ink && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="type-identifier text-xs">ink</span>
            <Hex>{palette[role.name]}</Hex>
          </div>
          <div className="flex flex-wrap gap-3">
            {ink.surfaces.map((key) => {
              const surface = findSurface(key)
              const surfaceHex = palette[key]
              return (
                <div key={key} className={cx(chipShell, surface.bg)}>
                  <span className={cx('type-body text-sm', ink.roleClass)}>Text</span>
                  <span className="type-identifier text-xs">{surface.label}</span>
                  <span className="type-identifier text-xs">
                    {formatRatio(palette[role.name], surfaceHex)} · floor 4.5
                  </span>
                </div>
              )
            })}
          </div>
          <Text role="supporting">{ink.note}</Text>
        </div>
      )}

      {border && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="type-identifier text-xs">border</span>
            <Hex>{palette[role.name]}</Hex>
          </div>
          <div className="flex flex-wrap gap-3">
            {border.surfaces.map((key) => {
              const surface = findSurface(key)
              const surfaceHex = palette[key]
              return (
                <div
                  key={key}
                  className={cx(chipShell, surface.bg, 'border-hairline', border.borderClass)}
                >
                  <span className="type-identifier text-xs">{surface.label}</span>
                  <span className="type-identifier text-xs">
                    {formatRatio(palette[role.name], surfaceHex)} · floor 3
                  </span>
                </div>
              )
            })}
          </div>
          <Text role="supporting">{border.note}</Text>
        </div>
      )}
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
  render: (_args, context) => {
    const theme = context.globals.theme === 'dark' ? 'dark' : 'light'
    const palette: Palette = color[theme]

    return (
      <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
        <Section
          heading="Colour"
          description="Every semantic role, what it means, the surfaces it may be painted on, its hex value in the active theme and its declared pairs' live contrast ratio. Reasoning and the full derivation: specs/README.md and specs/color-tokens.md."
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
                  <Hex>{palette[surface.name as ColorRoleKey]}</Hex>
                  <span className="type-supporting text-xs text-text-secondary">
                    {surface.meaning}
                  </span>
                </div>
              ))}
            </div>
          </Section>

          <Section
            heading="Text and lines"
            description="Normal text owes 4.5:1 against every surface it declares; a role held below that floor by design (text-disabled) states its own floor instead. Each tile's ratio is computed live from the two hexes above it — nothing here is copied from a table."
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {INK_ROLES.map((role) => (
                <div key={role.name}>{InkRoleCard(role, palette)}</div>
              ))}
            </div>
          </Section>

          <Section
            heading="Boundaries, painted as a border"
            description="A boundary, stripe or ring owes the 3:1 non-text floor (WCAG 1.4.11) against every surface it declares."
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {BOUNDARY_ROLES.map((role) => (
                <div key={role.name}>{BoundaryRoleCard(role, palette)}</div>
              ))}
            </div>
          </Section>

          <Section heading="Focus ring, painted as a ring">
            <div className="flex flex-wrap items-baseline gap-2">
              <RoleName>focus-ring</RoleName>
              <Hex>{palette['focus-ring']}</Hex>
              <Text role="supporting">
                Clears the 3:1 non-text floor against every page surface it declares (DS-10,
                color-tokens.md §5). Does not declare accent — an accent-filled control rings inward
                with accent-contrast instead (Button's primary variant).
              </Text>
            </div>
            <div className="flex flex-wrap gap-3">
              {PAGE_SURFACES.map((surface) => {
                const surfaceHex = palette[surface.key as ColorRoleKey]
                return (
                  <div
                    key={surface.key}
                    className={cx(
                      chipShell,
                      surface.bg,
                      'outline outline-ring outline-offset-ring outline-focus-ring',
                    )}
                  >
                    <span className="type-identifier text-xs">{surface.label}</span>
                    <span className="type-identifier text-xs">
                      {formatRatio(palette['focus-ring'], surfaceHex)} · floor 3
                    </span>
                  </div>
                )
              })}
            </div>
          </Section>

          <Section
            heading="Emphasis and status"
            description="Grouped by the shape a role is actually painted in — fill, ink or border — and captioned with the real surface, found by reading every call site in packages/design-system/src rather than assuming a role's most natural shape. A role's declared surfaces are only the ones a component paints it on today: warning and info have one (Callout and Badge, both unconditionally surface-raised); success and danger have four, because MatchRow and ProfileSummary also paint them directly onto the page. That is the same rule applied to every row below, not an exception for any one of them."
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {STATUS_ROLES.map((role) => (
                <div key={role.name}>{StatusRoleCard(role, palette)}</div>
              ))}
            </div>
          </Section>

          <Section
            heading="Overlay"
            description="A scrim that removes the page beneath a modal — Dialog's backdrop, Menu's mobile backdrop. Carries no foreground: nothing is read against a scrim, so no ratio applies to it."
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <RoleName>overlay</RoleName>
              <Hex>{palette.overlay}</Hex>
            </div>
            <div className="relative h-32 w-64 overflow-hidden rounded-panel border-hairline border-border">
              <div className="flex h-full items-center justify-center bg-surface">
                <span className="type-body text-sm text-text-primary">Page content</span>
              </div>
              <div className="absolute inset-0 flex items-center justify-center bg-overlay">
                {/* The scrim itself carries no ink (README: "nothing is read against a scrim") —
                    what reads is the dialog's own surface-raised panel sitting on top of it,
                    exactly as Dialog composes it, never text painted on the overlay fill
                    directly. */}
                <div className="rounded-panel bg-surface-raised px-3 py-2 shadow-modal">
                  <span className="type-body text-sm text-text-primary">Dialog above</span>
                </div>
              </div>
            </div>
          </Section>

          <Section
            heading="Player colours"
            description="A player's own colour, theme-invariant — the fill and its ink carry one value in both themes because a player's colour is their identity, not a mood. Framed in border-strong, per player-colour-swatch.md. Every fill/ink pair clears the 4.5:1 floor a glyph on the swatch needs (build-tokens.test.mjs)."
          >
            <div className="flex flex-wrap gap-3">
              {PLAYER_COLOURS.map((player) => {
                const fillHex = palette[player.name as ColorRoleKey]
                const inkHex = palette[`${player.name}-contrast` as ColorRoleKey]
                return (
                  <div
                    key={player.name}
                    className={cx(
                      'flex h-24 w-24 flex-col items-center justify-center gap-1 rounded-control border-hairline border-border-strong text-xs',
                      player.swatch,
                      player.ink,
                    )}
                  >
                    <span>{player.label}</span>
                    <span className="type-machine text-xs">{fillHex}</span>
                    <span className="type-machine text-xs">{formatRatio(inkHex, fillHex)}</span>
                  </div>
                )
              })}
            </div>
          </Section>
        </Section>
      </div>
    )
  },
}
