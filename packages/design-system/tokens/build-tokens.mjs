#!/usr/bin/env node
// Token generator (T016, extended T512). Reads the JSON source of truth in
// packages/design-system/tokens/*.json and writes packages/design-system/tokens/generated/
// {tokens.css,preset.css,tokens.ts}: CSS custom properties for every family, the Tailwind preset
// that maps them onto Tailwind's own theme namespaces (including `@utility` blocks for a family
// Tailwind has no namespace for, and `--animate-*` mappings with their `@keyframes`), and typed
// TypeScript accessors for the rare consumer that isn't a Tailwind utility class (design-system
// skill: "generated into CSS variables and TypeScript types").
//
// Run with `pnpm --filter design-system tokens:build` after editing any *.json in this directory.
// Zero dependencies on purpose: this script must run before `pnpm install` has finished resolving
// anything else in the workspace.
//
// Families read defensively (see `readJsonSafe`): `breakpoint.json`, `border.json`, `size.json`
// and motion.json's `animation` group are 005 additions that do not all exist in every checkout
// yet (contracts/token-families.md §1). A missing one degrades to no output for the shape it
// feeds, never a crash. Most of these need no further edit here once their JSON lands — but
// `border.json` (T514) is the one exception: it has no Tailwind theme namespace to extend (no
// `--border-width-*`, unlike `--radius-*`), so it needed its own `borderVars` and
// `borderUtilityBlocks` below rather than reusing an existing flat-family code path.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const tokensDir = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.join(tokensDir, 'generated')

const CSS_BANNER = [
  '/* GENERATED FILE — do not hand-edit.',
  ' * Source: packages/design-system/tokens/*.json',
  ' * Regenerate with `pnpm --filter design-system tokens:build`. */',
].join('\n')

const TS_BANNER = [
  '// GENERATED FILE — do not hand-edit.',
  '// Source: packages/design-system/tokens/*.json',
  '// Regenerate with `pnpm --filter design-system tokens:build`.',
].join('\n')

// `$comment` is metadata for humans reading the JSON, never a token — strip any `$`-prefixed key
// at the top level so a flat family (radius.json) doesn't emit it as a CSS variable.
function readJson(name) {
  const data = JSON.parse(readFileSync(path.join(tokensDir, `${name}.json`), 'utf8'))
  return Object.fromEntries(Object.entries(data).filter(([key]) => !key.startsWith('$')))
}

// Same as `readJson`, but a family whose JSON file does not exist yet degrades to `null` rather
// than crashing the build. Every 005 family this generator learns about before its JSON lands
// (breakpoint, size) is read this way, so the follow-up task that adds the file needs no further
// change here — a malformed file that *does* exist still throws, deliberately.
function readJsonSafe(name) {
  try {
    return readJson(name)
  } catch (err) {
    if (err.code === 'ENOENT') return null
    throw err
  }
}

// CSS custom property names are permissive, but keeping this to [a-z0-9-] avoids ever having to
// think about escaping — the same reason component code never sees a raw token key either.
function cssKey(key) {
  return String(key)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
}

function cssVar(name) {
  return `--ds-${name}`
}

const color = readJson('color')
const space = readJson('space')
const radius = readJson('radius')
const icon = readJson('icon')
const font = readJson('font')
const elevation = readJson('elevation')
const motion = readJson('motion')

// 005 additions — see the header comment and contracts/token-families.md §1. `breakpoint.json`
// (T513), `border.json` (T514) and `size.json` (T515) do not exist in every checkout yet;
// `motion.json` already exists, but its `animation` group (T516) is optional until that task
// adds it.
const breakpoint = readJsonSafe('breakpoint')
const border = readJsonSafe('border')
const size = readJsonSafe('size')
const animation = motion.animation ?? null

// --- Flat { cssVarName: value } maps, one per family, themed families keyed by theme first. ---

function colorVars(theme) {
  const entries = Object.entries(color[theme]).map(([key, value]) => [
    cssVar(`color-${cssKey(key)}`),
    value,
  ])
  return Object.fromEntries(entries)
}

function elevationVars(theme) {
  const entries = Object.entries(elevation[theme]).map(([key, value]) => [
    cssVar(`elevation-${cssKey(key)}`),
    value,
  ])
  return Object.fromEntries(entries)
}

function spaceVars() {
  const entries = [[cssVar('space-unit'), space.unit]]
  for (const [key, value] of Object.entries(space.scale)) {
    entries.push([cssVar(`space-${cssKey(key)}`), value])
  }
  return Object.fromEntries(entries)
}

function radiusVars() {
  return Object.fromEntries(
    Object.entries(radius).map(([key, value]) => [cssVar(`radius-${cssKey(key)}`), value]),
  )
}

function iconVars() {
  return Object.fromEntries(
    Object.entries(icon).map(([key, value]) => [cssVar(`icon-${cssKey(key)}`), value]),
  )
}

function fontVars() {
  const entries = []
  for (const [key, value] of Object.entries(font.family)) {
    entries.push([cssVar(`font-family-${cssKey(key)}`), value])
  }
  for (const [key, { value, lineHeight }] of Object.entries(font.size)) {
    entries.push([cssVar(`font-size-${cssKey(key)}`), value])
    entries.push([cssVar(`font-size-${cssKey(key)}-line-height`), lineHeight])
  }
  for (const [key, value] of Object.entries(font.weight)) {
    entries.push([cssVar(`font-weight-${cssKey(key)}`), value])
  }
  for (const [key, value] of Object.entries(font.tracking)) {
    entries.push([cssVar(`font-tracking-${cssKey(key)}`), value])
  }
  return Object.fromEntries(entries)
}

// `@font-face` blocks, one per `font.face` entry (typography-tokens.md §8.1, §14 step 5). Emitted
// at the top of tokens.css, before `:root`, so both consumers — apps/web's index.css and
// Storybook's preview.tsx — receive the rules through the one stylesheet they already import
// (`preset.css` opens with `@import './tokens.css'`), with no consumer gaining a font import of
// its own. `format('woff2')` and not the hinted `tech(variations)`/`woff2-variations` forms
// (§8.1); an absolute `url()`, never bundler-relative, because these files are served as static
// assets under a fixed prefix in both consumers (§8.3) rather than resolved through a bundler.
function fontFaceRules() {
  return Object.values(font.face)
    .map(
      (face) => `@font-face {
  font-family: '${face.family}';
  src: url('${face.src}') format('woff2');
  font-weight: ${face.weight};
  font-style: ${face.style};
  font-display: ${face.display};
}`,
    )
    .join('\n\n')
}

function motionVars() {
  const entries = []
  for (const [key, value] of Object.entries(motion.duration)) {
    entries.push([cssVar(`motion-duration-${cssKey(key)}`), value])
  }
  for (const [key, value] of Object.entries(motion.easing)) {
    entries.push([cssVar(`motion-easing-${cssKey(key)}`), value])
  }
  return Object.fromEntries(entries)
}

// Breakpoints are not themed — a viewport width does not change with `data-theme` — so this is a
// flat family like radius or icon. tokens.css still carries `--ds-breakpoint-*` for consistency
// with every other family (contracts/token-families.md §1), even though nothing in the cascade
// reads it back: Tailwind's own `--breakpoint-*` mapping in preset.css cannot be a var() reference
// (see the comment beside it below) and carries the literal value instead. Both come from this
// same object, in this same generator run, so they cannot drift apart.
function breakpointVars() {
  if (!breakpoint) return {}
  return Object.fromEntries(
    Object.entries(breakpoint).map(([key, value]) => [
      cssVar(`breakpoint-${cssKey(key)}`),
      `${value}px`,
    ]),
  )
}

// Container, panel and reading-measure widths (DS-6). Flat, untheme, mapped onto Tailwind's own
// `--container-*` namespace below so `max-w-page` / `max-w-panel` / `max-w-measure` are ordinary
// utilities.
function sizeVars() {
  if (!size) return {}
  return Object.fromEntries(
    Object.entries(size).map(([key, value]) => [cssVar(`size-${cssKey(key)}`), value]),
  )
}

// Border, focus-ring and focus-ring-offset widths (DS-4). Flat, untheme, same shape as
// `radiusVars` — but unlike radius there is no Tailwind theme namespace to map these onto
// (`--radius-*` is a real namespace in Tailwind's own theme.css; `--border-width-*`,
// `--outline-width-*` and `--outline-offset-*` are not), so these three variables are consumed
// through the `@utility` blocks below rather than through `@theme inline`.
function borderVars() {
  if (!border) return {}
  return Object.fromEntries(
    Object.entries(border).map(([key, value]) => [cssVar(`border-${cssKey(key)}`), value]),
  )
}

function renderBlock(vars, indent = '  ') {
  return Object.entries(vars)
    .map(([name, value]) => `${indent}${name}: ${value};`)
    .join('\n')
}

const rootVars = {
  ...spaceVars(),
  ...radiusVars(),
  ...iconVars(),
  ...fontVars(),
  ...motionVars(),
  ...breakpointVars(),
  ...borderVars(),
  ...sizeVars(),
  ...colorVars('light'),
  ...elevationVars('light'),
  // typography-tokens.md §7.3, §8.1: every declared weight (400-700) is a real interpolation of
  // the shipped weight axis, so nothing ever needs synthesis. This is small hardening rather than
  // load-bearing — its only job is to make a future missing weight fail visibly instead of being
  // faked into a smeared approximation nobody notices.
  'font-synthesis-weight': 'none',
}
const darkVars = {
  ...colorVars('dark'),
  ...elevationVars('dark'),
}

const tokensCss = `${CSS_BANNER}
/* Self-hosted @font-face declarations (typography-tokens.md §8.1). Ahead of :root so the browser
 * discovers them before anything below requests the family they declare. */
${fontFaceRules()}

/* Untheme families (space, radius, icon, font, motion) plus the light theme's colour and elevation
 * — light is the default so a component works before any theme is chosen. */
:root {
${renderBlock(rootVars)}
}

/* Same variable names, dark values. Set data-theme="dark" on <html> or any ancestor; nothing
 * downstream needs to know which theme is active (design-system skill, "Tokens"). */
[data-theme='dark'] {
${renderBlock(darkVars)}
}
`
mkdirSync(outDir, { recursive: true })
writeFileSync(path.join(outDir, 'tokens.css'), tokensCss)

// --- Tailwind v4 preset: maps our --ds-* variables onto Tailwind's own theme namespaces, using
// `@theme inline` (not `@theme`) so the mapping stays a live var() reference — the whole point of
// the dark theme override above being a plain CSS cascade and not a rebuild. ---

function themeEntries(prefix, keys, dsPrefix) {
  return keys.map(
    (key) => `  --${prefix}-${cssKey(key)}: var(${cssVar(`${dsPrefix}-${cssKey(key)}`)});`,
  )
}

const themeLines = [
  '  /* space — the single multiplier every numeric utility (p-3, gap-4, ...) is computed from */',
  `  --spacing: var(${cssVar('space-unit')});`,
  '',
  '  /* color */',
  ...themeEntries('color', Object.keys(color.light), 'color'),
  '',
  '  /* radius */',
  ...themeEntries('radius', Object.keys(radius), 'radius'),
  '',
  '  /* icon — no Tailwind theme namespace maps a fixed size scale onto width, height or size',
  '   * utilities the way radius maps onto rounded-*, so there is nothing to add here. Icon sizes',
  "   * are reachable as ordinary classes (icon-xs … icon-3xl) through the @utility blocks below",
  '   * instead, and through iconTokens / --ds-icon-* for the rare non-utility consumer. */',
  '',
  '  /* font */',
  ...Object.keys(font.family).map(
    (key) => `  --font-${cssKey(key)}: var(${cssVar(`font-family-${cssKey(key)}`)});`,
  ),
  ...Object.keys(font.size).flatMap((key) => [
    `  --text-${cssKey(key)}: var(${cssVar(`font-size-${cssKey(key)}`)});`,
    `  --text-${cssKey(key)}--line-height: var(${cssVar(`font-size-${cssKey(key)}-line-height`)});`,
  ]),
  ...Object.keys(font.weight).map(
    (key) => `  --font-weight-${cssKey(key)}: var(${cssVar(`font-weight-${cssKey(key)}`)});`,
  ),
  ...Object.keys(font.tracking).map(
    (key) => `  --tracking-${cssKey(key)}: var(${cssVar(`font-tracking-${cssKey(key)}`)});`,
  ),
  '',
  '  /* elevation */',
  ...themeEntries('shadow', Object.keys(elevation.light), 'elevation'),
  '',
  '  /* motion — easings only; durations are used as bare Tailwind numbers (duration-120), see',
  '   * tokens/motion.json and tokens.ts for the closed set a component picks from */',
  ...Object.keys(motion.easing).map(
    (key) => `  --ease-${cssKey(key)}: var(${cssVar(`motion-easing-${cssKey(key)}`)});`,
  ),
  ...(size
    ? [
        '',
        "  /* size — container widths, mapped onto Tailwind's own --container-* namespace so",
        '   * max-w-page / max-w-panel / max-w-measure are ordinary utilities */',
        ...themeEntries('container', Object.keys(size), 'size'),
      ]
    : []),
  ...(animation
    ? [
        '',
        "  /* motion — looping animations, mapped onto Tailwind's own --animate-* namespace so",
        "   * animate-spin / animate-pulse derive from this file's durations instead of Tailwind's",
        "   * built-in ones. Each one's @keyframes are emitted below, outside this theme block —",
        '   * a keyframe selector and its declarations are not var() references. */',
        ...animationThemeLines(),
      ]
    : []),
]

// Breakpoints are the one Tailwind theme namespace that cannot take a var() reference: Tailwind
// embeds this value literally into a generated `@media (width >= …)` rule, and a media query
// cannot read a CSS custom property. Every mapping in `@theme inline` above lives there for
// exactly the opposite reason — so it stays a live var() reference across a theme switch — but a
// breakpoint is not themed, so there is nothing for it to switch, and Tailwind requires the
// literal number regardless. `tokens/breakpoint.json` is still the one source of truth: this and
// `--ds-breakpoint-*` in tokens.css both come from the same object in the same generator run, so
// the two cannot drift apart even though this copy is a literal rather than a reference.
function breakpointThemeBlock() {
  if (!breakpoint) return null
  const lines = Object.entries(breakpoint).map(
    ([key, value]) => `  --breakpoint-${cssKey(key)}: ${value}px;`,
  )
  return `@theme {\n${lines.join('\n')}\n}`
}

// `@utility` — Tailwind v4's mechanism for a fixed-value custom utility class with no matching
// theme namespace to extend (contracts/token-families.md §1, §2). Icon sizes are one family that
// needs it: no Tailwind namespace maps a fixed scale onto width/height/size utilities the way
// `radius` maps onto `rounded-*`, so each step becomes its own utility instead.
function iconUtilityBlocks() {
  return Object.keys(icon).map((key) => {
    const varName = cssVar(`icon-${cssKey(key)}`)
    return `@utility icon-${cssKey(key)} {\n  width: var(${varName});\n  height: var(${varName});\n}`
  })
}

// `border.json` (DS-4) is the other family with no theme namespace to extend — Tailwind exposes
// no `--border-width-*`, `--outline-width-*` or `--outline-offset-*` namespace the way it exposes
// `--radius-*`, and its own border-width/outline-width/outline-offset utilities are an unbounded
// numeric scale rather than a themed one (research D5). Unlike icon's uniform "one step, one
// width-and-height utility" shape, this family's three keys each need a different CSS property
// and a utility name distinct from the JSON key, so this stays a literal mapping rather than a
// generic loop — the utility names are fixed by contracts/token-families.md §2, not derived.
function borderUtilityBlocks() {
  if (!border) return []
  const utilities = [
    ['hairline', 'border-hairline', 'border-width'],
    ['ring', 'outline-ring', 'outline-width'],
    ['ring-offset', 'outline-offset-ring', 'outline-offset'],
  ]
  return utilities
    .filter(([key]) => key in border)
    .map(([key, utilityName, property]) => {
      const varName = cssVar(`border-${cssKey(key)}`)
      return `@utility ${utilityName} {\n  ${property}: var(${varName});\n}`
    })
}

// `font.role` (T524, FR-007, contracts/token-families.md §4, research D7): one `@utility
// type-<role>` block per typographic role, keyed by function rather than by size. Every block sets
// its family; `numeric` alone adds `font-variant-numeric: tabular-nums` (declaring it on a role
// shared with `machine` would apply it to filenames and error classes, where it means nothing) and
// `identifier` alone adds a `color` — the one utility in this vocabulary that sets a property
// outside typography, a deliberate widening so an unobserved value stays visibly distinct from a
// measured one even for a caller who never reads its spec. Same shape as `iconUtilityBlocks` and
// `borderUtilityBlocks` above: a family with no Tailwind theme namespace to extend, so each entry
// becomes its own fixed-value utility instead.
function typeRoleUtilityBlocks() {
  if (!font.role) return []
  return Object.entries(font.role).map(([key, role]) => {
    const declarations = [`  font-family: var(${cssVar(`font-family-${cssKey(role.family)}`)});`]
    if (role.variantNumeric) {
      declarations.push(`  font-variant-numeric: ${role.variantNumeric};`)
    }
    if (role.color) {
      declarations.push(`  color: var(${cssVar(`color-${cssKey(role.color)}`)});`)
    }
    return `@utility type-${cssKey(key)} {\n${declarations.join('\n')}\n}`
  })
}

// The `@keyframes` a looping `--animate-*` mapping names. Declarations here are literal CSS
// values (a transform, an opacity), not design tokens, so — unlike every var() mapping above —
// there is nothing to reference back to tokens.css.
function animationKeyframeBlocks() {
  if (!animation) return []
  return Object.entries(animation).map(([name, def]) => {
    const steps = Object.entries(def.keyframes)
      .map(([selector, declarations]) => {
        const body = Object.entries(declarations)
          .map(([property, value]) => `    ${property}: ${value};`)
          .join('\n')
        return `  ${selector} {\n${body}\n  }`
      })
      .join('\n')
    return `@keyframes ds-${cssKey(name)} {\n${steps}\n}`
  })
}

// The `--animate-*` var() mappings themselves, composing a duration and an easing from this same
// file so FR-010's "every duration comes from the motion family" holds for loops as well as
// transitions.
function animationThemeLines() {
  if (!animation) return []
  return Object.entries(animation).map(([name, def]) => {
    const duration = cssVar(`motion-duration-${cssKey(def.duration)}`)
    const easing = cssVar(`motion-easing-${cssKey(def.easing)}`)
    return `  --animate-${cssKey(name)}: ds-${cssKey(name)} var(${duration}) var(${easing}) ${def.iterationCount};`
  })
}

const presetSections = [
  `@theme inline {\n${themeLines.join('\n')}\n}`,
  breakpointThemeBlock(),
  ...animationKeyframeBlocks(),
  ...iconUtilityBlocks(),
  ...borderUtilityBlocks(),
  ...typeRoleUtilityBlocks(),
].filter(Boolean)

const presetCss = `${CSS_BANNER}
@import './tokens.css';

${presetSections.join('\n\n')}
`
writeFileSync(path.join(outDir, 'preset.css'), presetCss)

// --- Typed TS accessors. Values are var() references, not literals: the resolved value still
// depends on which theme is active, which is a CSS cascade concern, not a JS one. ---

function tsObject(vars, indent = '  ') {
  return Object.entries(vars)
    .map(([key, name]) => `${indent}'${key}': 'var(${name})',`)
    .join('\n')
}

function keyed(obj, cssPrefix, dsPrefix) {
  return Object.fromEntries(
    Object.keys(obj).map((key) => [key, cssVar(`${dsPrefix}-${cssKey(key)}`)]),
  )
}

const colorTs = keyed(color.light, 'color', 'color')
const spaceTs = { unit: cssVar('space-unit'), ...keyed(space.scale, 'space', 'space') }
const radiusTs = keyed(radius, 'radius', 'radius')
const iconTs = keyed(icon, 'icon', 'icon')
const elevationTs = keyed(elevation.light, 'elevation', 'elevation')
const fontFamilyTs = keyed(font.family, 'font-family', 'font-family')
const fontSizeTs = Object.fromEntries(
  Object.keys(font.size).map((key) => [key, cssVar(`font-size-${cssKey(key)}`)]),
)
const fontWeightTs = keyed(font.weight, 'font-weight', 'font-weight')
const fontTrackingTs = keyed(font.tracking, 'font-tracking', 'font-tracking')
const motionDurationTs = keyed(motion.duration, 'motion-duration', 'motion-duration')
const motionEasingTs = keyed(motion.easing, 'motion-easing', 'motion-easing')

const tokensTs = `${TS_BANNER}
// Every value below is a CSS var() reference, not a literal — the resolved value depends on the
// active theme (light by default, dark under [data-theme='dark']). See tokens/generated/tokens.css.

export const colorTokens = {
${tsObject(colorTs)}
} as const
export type ColorToken = keyof typeof colorTokens

export const spaceTokens = {
${tsObject(spaceTs)}
} as const
export type SpaceToken = keyof typeof spaceTokens

export const radiusTokens = {
${tsObject(radiusTs)}
} as const
export type RadiusToken = keyof typeof radiusTokens

export const iconTokens = {
${tsObject(iconTs)}
} as const
export type IconToken = keyof typeof iconTokens

export const elevationTokens = {
${tsObject(elevationTs)}
} as const
export type ElevationToken = keyof typeof elevationTokens

export const fontTokens = {
  family: {
${tsObject(fontFamilyTs, '    ')}
  },
  size: {
${tsObject(fontSizeTs, '    ')}
  },
  weight: {
${tsObject(fontWeightTs, '    ')}
  },
  tracking: {
${tsObject(fontTrackingTs, '    ')}
  },
} as const

export const motionTokens = {
  duration: {
${tsObject(motionDurationTs, '    ')}
  },
  easing: {
${tsObject(motionEasingTs, '    ')}
  },
} as const
${
  breakpoint
    ? `
// EXCEPTION to the var()-only rule above. Every other export in this file is a var() reference
// because its resolved value depends on the active theme — a CSS cascade concern this file leaves
// to tokens.css. A breakpoint is not themed: it does not change when \`data-theme\` does. It is
// consumed by \`matchMedia\`, which needs a plain number of pixels — a CSS custom property is not a
// value \`matchMedia\` can read — so this is the one generated export that is a raw number rather
// than a \`var()\` reference, and it should be the only one. useMediaQuery.ts imports this instead
// of hard-coding its own copy (DS-5), so styling (preset.css's --breakpoint-* mapping, also a
// literal for the same matchMedia-shaped reason) and structure derive from the one file.
export const breakpointTokens = {
${Object.entries(breakpoint)
  .map(([key, value]) => `  '${key}': ${Number(value)},`)
  .join('\n')}
} as const
export type BreakpointToken = keyof typeof breakpointTokens
`
    : ''
}`
writeFileSync(path.join(outDir, 'tokens.ts'), tokensTs)

console.log(
  `tokens: wrote ${path.relative(process.cwd(), outDir)}/{tokens.css,preset.css,tokens.ts}`,
)
