#!/usr/bin/env node
// T541: FR-028 makes a component's tier — primitive, domain composite or screen — determine where
// it lives in the filesystem (T540 carried that assignment into
// `packages/design-system/src/{primitives,composites,screens}/`); FR-029 then states the one
// dependency rule the tier exists to buy: a primitive MUST NOT depend on a domain composite or a
// screen, and no component MUST depend on the application. Neither half is enforceable from a
// manifest that names each component's tier — a manifest is a second home for a fact the
// filesystem already carries, and this repository's law is that a fact written twice goes stale in
// one copy. The filesystem *is* the boundary, so this check reads it directly: every import
// specifier in every source file under `packages/design-system/src/`, resolved the same way a
// bundler would resolve it, and classified against the two forbidden shapes below.
//
// What it checks, and how a specifier is resolved:
//   1. A file under `src/primitives/` importing a specifier that resolves (relatively) into
//      `src/composites/` or `src/screens/`.
//   2. A file anywhere under `src/` importing a specifier that resolves (relatively) into the
//      repository's `apps/` root, or a bare specifier naming one of the workspace's own `apps/*`
//      package names (`web`, from `apps/web/package.json`'s unscoped `"name"` — this monorepo has
//      no scoped package names to disambiguate a bare import from an npm package of the same name,
//      so the bare-specifier check is deliberately narrow: only names this workspace's own `apps/*`
//      manifests actually declare, not a generic word list).
// A relative specifier (`.`/`..`) is resolved with `path.resolve` against the importing file's own
// directory — the same rule a bundler applies — which is enough to classify it without touching
// the filesystem for extension or `index` resolution: `../../composites/SiteHeader` from
// `src/primitives/Badge/index.tsx` resolves to `src/composites/SiteHeader`, already under the tier
// prefix this check compares against.
//
// Scope. Every `.ts`/`.tsx` file under `packages/design-system/src/` is scanned — implementation,
// story and test files alike, unlike `token-scale.mjs`'s implementation-only scope. A story or a
// test is still part of the package a consumer's bundler resolves, and an import the boundary
// forbids is exactly as real a dependency from a `.stories.tsx` file as from `index.tsx`.
//
// Method. A line-based scan for `import`/`export ... from '<specifier>'` and bare `import
// '<specifier>'` statements, the same lexical approach `token-scale.mjs`'s header explains this
// repository's checks favour over a full TypeScript AST: import declarations in this codebase are
// always whole statements, never built from a template literal or a computed value, so a regular
// expression finds every one of them.
//
// Usage:  node scripts/checks/tier-deps.mjs
// Exit:   0 if no primitive imports a composite or a screen and nothing under `src/` imports from
//         `apps/`, 1 otherwise — every finding names both the importing file and the disallowed
//         import target.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')
const appsDir = path.join(rootDir, 'apps')
const primitivesDir = path.join(srcDir, 'primitives')
const compositesDir = path.join(srcDir, 'composites')
const screensDir = path.join(srcDir, 'screens')

// Bare specifiers that name one of this workspace's own `apps/*` packages by their (unscoped)
// `package.json` "name" — see the file header for why this is a narrow, named list rather than a
// heuristic over the word "apps".
const APP_PACKAGE_NAMES = new Set(['web'])

function log(message) {
  console.log(`tier-deps: ${message}`)
}

function fail(message) {
  console.error(`tier-deps: ${message}`)
  process.exitCode = 1
}

// --- File discovery -------------------------------------------------------------------------

export function listSourceFiles(dir) {
  const results = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      results.push(...listSourceFiles(full))
    } else if (entry.endsWith('.ts') || entry.endsWith('.tsx')) {
      results.push(full)
    }
  }
  return results
}

// --- Import-specifier extraction -------------------------------------------------------------

// Matches `import ... from '<spec>'`, `export ... from '<spec>'` and bare `import '<spec>'`,
// single- or double-quoted. Anchored to the start of a (trimmed) line, which every import
// declaration in this codebase's source files is — none is built from a template literal or a
// computed value (see the file header).
const IMPORT_LINE_RE = /^(?:import|export)\b[^'"]*from\s+['"]([^'"]+)['"]|^import\s+['"]([^'"]+)['"]/

export function extractImportSpecifiers(source) {
  const specifiers = []
  const lines = source.split('\n')
  for (const line of lines) {
    const match = IMPORT_LINE_RE.exec(line.trim())
    if (match) specifiers.push(match[1] ?? match[2])
  }
  return specifiers
}

// --- Classification ---------------------------------------------------------------------------

// Resolves an import specifier against the file that carries it. Relative specifiers resolve to
// an absolute path (bundler rule); bare specifiers pass through unresolved, since this check only
// ever needs to compare a bare specifier against the narrow `APP_PACKAGE_NAMES` list, never a
// filesystem path.
function resolveSpecifier(filePath, specifier) {
  if (specifier.startsWith('.')) {
    return path.resolve(path.dirname(filePath), specifier)
  }
  return specifier
}

function isUnder(candidate, dir) {
  const rel = path.relative(dir, candidate)
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel))
}

function isBareAppPackage(specifier) {
  const [pkg] = specifier.split('/')
  return APP_PACKAGE_NAMES.has(pkg)
}

// One finding per (file, specifier) violation, describing which rule it breaks and both ends of
// the violation.
export function checkImport(filePath, specifier) {
  const resolved = resolveSpecifier(filePath, specifier)
  const findings = []

  const resolvedIsPath = typeof resolved === 'string' && path.isAbsolute(resolved)
  const targetsApps =
    (resolvedIsPath && isUnder(resolved, appsDir)) || (!resolvedIsPath && isBareAppPackage(specifier))
  if (targetsApps) {
    findings.push(
      `${path.relative(rootDir, filePath)} imports \`${specifier}\` — a dependency on the ` +
        `application. No component under packages/design-system/src/ may depend on apps/ (FR-029).`,
    )
  }

  if (resolvedIsPath && isUnder(filePath, primitivesDir)) {
    if (isUnder(resolved, compositesDir)) {
      findings.push(
        `${path.relative(rootDir, filePath)} (a primitive) imports \`${specifier}\` -> ` +
          `${path.relative(rootDir, resolved)} (a domain composite). A primitive MUST NOT depend ` +
          `on a domain composite (FR-029).`,
      )
    } else if (isUnder(resolved, screensDir)) {
      findings.push(
        `${path.relative(rootDir, filePath)} (a primitive) imports \`${specifier}\` -> ` +
          `${path.relative(rootDir, resolved)} (a screen). A primitive MUST NOT depend on a ` +
          `screen (FR-029).`,
      )
    }
  }

  return findings
}

export function checkFile(filePath, source) {
  const findings = []
  for (const specifier of extractImportSpecifiers(source)) {
    findings.push(...checkImport(filePath, specifier))
  }
  return findings
}

function main() {
  const files = listSourceFiles(srcDir)
  let total = 0
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const message of checkFile(file, source)) {
      total++
      fail(message)
    }
  }
  if (total > 0) {
    fail(
      `${total} tier-boundary violation${total === 1 ? '' : 's'} found across ` +
        `${path.relative(rootDir, srcDir)}.`,
    )
    return
  }
  log(
    `${files.length} files under ${path.relative(rootDir, srcDir)} respect the tier boundary — ` +
      'no primitive imports a composite or a screen, and nothing imports from apps/.',
  )
}

// Only run when invoked directly (`node scripts/checks/tier-deps.mjs`) — a future test suite could
// import the functions above without triggering the scan or the process exit code, the same split
// `token-scale.mjs` uses.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
