#!/usr/bin/env node
// T693 piece 1: the source stamp (`packages/design-system/.storybook/source-stamp.mjs`) is a
// Storybook-only transform — nothing of it may reach the markup `apps/web` builds. This scans the
// built output (`apps/web/dist`, or the directory named by the first argument) for the attribute
// name and fails if any file carries it. It needs the built app, so CI runs it right after
// `pnpm --filter web build`; `scripts/visual/source-stamp.test.mjs` plants a directory to prove the
// scan fires and stays silent.
//
// Usage:  node scripts/checks/stamp-absent.mjs [dir]
// Exit:   0 when no file carries the attribute, 1 when one does or the directory is missing.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// Every file under `dir` (relative to it) whose text names the stamp attribute.
export function findStampedFiles(dir) {
  const found = []
  const walk = (rel) => {
    for (const entry of readdirSync(path.join(dir, rel), { withFileTypes: true })) {
      const next = path.join(rel, entry.name)
      if (entry.isDirectory()) walk(next)
      else if (readFileSync(path.join(dir, next)).includes(STAMP_ATTRIBUTE)) found.push(next)
    }
  }
  walk('')
  return found.sort()
}

function main() {
  const dir = path.resolve(process.argv[2] ?? path.join(rootDir, 'apps', 'web', 'dist'))
  if (!existsSync(dir)) {
    console.log(
      `stamp-absent: ${dir} does not exist — build the app first (pnpm --filter web build).`,
    )
    process.exit(1)
  }
  const found = findStampedFiles(dir)
  if (found.length > 0) {
    console.log(`stamp-absent: ${found.length} built file(s) carry "${STAMP_ATTRIBUTE}":`)
    for (const f of found) console.log(`  - ${f}`)
    process.exit(1)
  }
  console.log(
    `stamp-absent: no built file under ${path.relative(rootDir, dir)} carries "${STAMP_ATTRIBUTE}".`,
  )
}

if (import.meta.url === `file://${process.argv[1]}`) main()
