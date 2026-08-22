#!/usr/bin/env node
// T107: fails when apps/web's built stylesheet carries the design tokens without the utilities
// the components are built from.
//
// Tailwind's automatic source detection stops at anything resolved through node_modules, and
// apps/web reaches the shared preset (packages/design-system/tokens/tailwind.css) exactly that
// way — as a workspace dependency, symlinked by pnpm. Left undeclared, neither
// packages/design-system/src nor apps/web/src is ever scanned, and the emitted stylesheet is
// almost entirely the ~50 token custom-property declarations (`--ds-color-*` etc): small, present,
// and therefore easy to mistake for a healthy build. Measured against that exact defect: 8547
// bytes, 51 token variables, and not one of the utilities below. A byte-size floor cannot catch
// this — the token block alone clears any plausible floor, which is precisely why the broken
// bundle looked populated. Only checking for the utilities themselves does.
//
// The asserted set is drawn from a frequency scan of every packages/design-system/src/components
// className, kept to utilities that are load-bearing for what the first production sign-in showed
// as broken: surface backgrounds, corner radius, layout primitives and the token-driven text
// colours and font families — not an exhaustive list of every class the library ever emits, which
// would drift out of sync with the components on its own.
//
// Usage:  node scripts/checks/built-css.mjs
// Exit:   0 if the built stylesheet contains every required utility, 1 otherwise.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const assetsDir = path.join(rootDir, 'apps', 'web', 'dist', 'assets')

// One representative per family the components rely on (see packages/design-system/skill and the
// className scan above), not every variant — a variant Tailwind fails to emit for an unrelated
// reason should not make this check indistinguishable from the T107 regression it exists to catch.
const REQUIRED_UTILITIES = [
  'bg-surface', // surface background — absent entirely in the T107 regression
  'rounded-lg', // corner radius — likewise absent entirely
  'rounded-full',
  'inline-flex', // layout primitive components are built from
  'text-text-primary', // token-driven text colour
  'text-text-secondary',
  'font-sans', // token-driven typography
  'border-border', // token-driven border colour
]

function log(message) {
  console.log(`built-css: ${message}`)
}

function findBuiltStylesheet() {
  if (!existsSync(assetsDir)) return null
  const cssFile = readdirSync(assetsDir).find((f) => f.endsWith('.css'))
  return cssFile ? path.join(assetsDir, cssFile) : null
}

function main() {
  const cssPath = findBuiltStylesheet()
  if (!cssPath) {
    log(
      `no built stylesheet found in ${path.relative(rootDir, assetsDir)} — run ` +
        '`pnpm --filter web build` first.',
    )
    process.exit(1)
  }

  const css = readFileSync(cssPath, 'utf8')
  const missing = REQUIRED_UTILITIES.filter((utility) => !css.includes(utility))

  if (missing.length > 0) {
    log(
      `${path.relative(rootDir, cssPath)} (${css.length} bytes) is missing utilities the ` +
        `design-system components use: ${missing.join(', ')}. This is the T107 defect — Tailwind's ` +
        'source detection is not scanning packages/design-system/src or apps/web/src. Check the ' +
        '@source directives in packages/design-system/tokens/tailwind.css and apps/web/src/index.css.',
    )
    process.exit(1)
  }

  log(`${path.relative(rootDir, cssPath)} (${css.length} bytes) carries every required utility.`)
}

main()
