#!/usr/bin/env node
// T693 piece 1: the source stamp (`packages/design-system/.storybook/source-stamp.mjs`, whose attribute name is
// defined in `source-stamp-attribute.cjs`) is a
// Storybook-only transform — nothing of it may reach the markup `apps/web` builds. This scans the
// built output (`apps/web/dist`, or the directory named by the first argument) for the attribute
// name and fails if any file carries it. It needs the built app, so CI runs it right after
// `pnpm --filter web build`; `scripts/visual/source-stamp.test.mjs` plants a directory to prove the
// scan fires and stays silent.
//
// A scan that found nothing to scan proves nothing: an empty or missing directory (a build that
// wrote its output elsewhere) fails as surely as a stamped one.
//
// Usage:  node scripts/checks/stamp-absent.mjs [dir]
// Exit:   0 when at least one file was scanned and none carries the attribute; 1 when one does, the
//         directory is missing, or it holds no file at all.
import { existsSync, readdirSync, readFileSync, realpathSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp-attribute.cjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// How many files under `dir` were scanned, and which of them (relative to it) name the stamp attribute.
export function scanDirectory(dir) {
  const found = []
  let scanned = 0
  const walk = (rel) => {
    for (const entry of readdirSync(path.join(dir, rel), { withFileTypes: true })) {
      const next = path.join(rel, entry.name)
      if (entry.isDirectory()) walk(next)
      else {
        scanned += 1
        if (readFileSync(path.join(dir, next)).includes(STAMP_ATTRIBUTE)) found.push(next)
      }
    }
  }
  walk('')
  return { scanned, found: found.sort() }
}

// Every file under `dir` (relative to it) whose text names the stamp attribute.
export function findStampedFiles(dir) {
  return scanDirectory(dir).found
}

function main() {
  const dir = path.resolve(process.argv[2] ?? path.join(rootDir, 'apps', 'web', 'dist'))
  if (!existsSync(dir)) {
    console.log(
      `stamp-absent: ${dir} does not exist — build the app first (pnpm --filter web build).`,
    )
    process.exit(1)
  }
  const { scanned, found } = scanDirectory(dir)
  if (scanned === 0) {
    console.log(
      `stamp-absent: ${dir} holds no file to scan — the build wrote its output elsewhere, or not at all.`,
    )
    process.exit(1)
  }
  if (found.length > 0) {
    console.log(`stamp-absent: ${found.length} built file(s) carry "${STAMP_ATTRIBUTE}":`)
    for (const f of found) console.log(`  - ${f}`)
    process.exit(1)
  }
  console.log(
    `stamp-absent: none of the ${scanned} file(s) under ${path.relative(rootDir, dir)} carries "${STAMP_ATTRIBUTE}".`,
  )
}

// `pathToFileURL` encodes what a path may contain (a space, a non-ASCII letter) the way `import.meta.url`
// is, which a hand-built `file://` prefix does not — and a script that silently does not run exits 0.
// `realpathSync` because Node reports the real path in `import.meta.url` while `argv[1]` keeps a
// symlink (macOS's `/var` is one) as typed.
if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) main()
