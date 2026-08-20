#!/usr/bin/env node
// Token generator (T016). Reads the JSON source of truth in packages/design-system/tokens/*.json
// and writes packages/design-system/tokens/generated/{tokens.css,tokens.ts}: CSS custom properties
// for every family, and typed TypeScript accessors for the rare consumer that isn't a Tailwind
// utility class (design-system skill: "generated into CSS variables and TypeScript types").
//
// Run with `pnpm --filter design-system tokens:build` after editing any *.json in this directory.
// Zero dependencies on purpose: this script must run before `pnpm install` has finished resolving
// anything else in the workspace.
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
const font = readJson('font')
const elevation = readJson('elevation')
const motion = readJson('motion')

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

function renderBlock(vars, indent = '  ') {
  return Object.entries(vars)
    .map(([name, value]) => `${indent}${name}: ${value};`)
    .join('\n')
}

const rootVars = {
  ...spaceVars(),
  ...radiusVars(),
  ...fontVars(),
  ...motionVars(),
  ...colorVars('light'),
  ...elevationVars('light'),
}
const darkVars = {
  ...colorVars('dark'),
  ...elevationVars('dark'),
}

const tokensCss = `${CSS_BANNER}
/* Untheme families (space, radius, font, motion) plus the light theme's colour and elevation —
 * light is the default so a component works before any theme is chosen. */
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
]

const presetCss = `${CSS_BANNER}
@import './tokens.css';

@theme inline {
${themeLines.join('\n')}
}
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
`
writeFileSync(path.join(outDir, 'tokens.ts'), tokensTs)

console.log(
  `tokens: wrote ${path.relative(process.cwd(), outDir)}/{tokens.css,preset.css,tokens.ts}`,
)
