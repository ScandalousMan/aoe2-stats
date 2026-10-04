// The pure half of the runtime pass's manifest (T693 piece 4): building entries, comparing them,
// merging a partial pass into the committed file and checking its keys against the built index. No
// browser and no filesystem except `formatManifest`'s call to this repository's own prettier, so
// `state-coverage-runtime-model.test.mjs` proves every rule here against small literals.
//
// The manifest is `packages/design-system/specs/state-coverage-runtime.json`: one entry per story id
// the built Storybook index lists (fixtures included — a plant's entry is what the browser rendered
// for it), in id order, each carrying the `importPath` and `exportName` the index gives that story —
// which is how T694 joins an entry to the story object it parses — and, per review width, what
// `tests/visual/state-coverage-runtime.ts` recorded: the match count and stamp of a forced story's
// target, the tracked primitive instance that placed it, what holds focus after `play()`, and every
// tracked primitive instance the story mounts. See that module for what each field means.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { importFile, listStories } from './story-index.mjs'

export const MANIFEST_PATH = 'packages/design-system/specs/state-coverage-runtime.json'
export const PASS_COMMAND = 'pnpm test:visual:state-coverage-runtime'
// The command that rewrites entries, named by every failure so the fix is never a guess.
export const REWRITE_COMMAND = `${PASS_COMMAND} --write`

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// One manifest entry for one index story, from what the browser recorded at each width.
export function buildEntry(story, widthRecords) {
  return {
    importPath: story.importPath,
    exportName: story.exportName,
    widths: Object.fromEntries(
      Object.entries(widthRecords)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([width, record]) => [String(width), record]),
    ),
  }
}

// Set equality between the manifest's keys and the stories the built index lists (fixtures
// included), and agreement on `importPath` and `exportName` for each: a story added, removed or
// renamed without its entry fails, whatever a diff selected. Returns one problem per disagreement,
// in id order, each `{ kind, id, detail }`.
export function findKeyProblems({ manifest, index }) {
  const stories = new Map(listStories(index, { includeFixtures: true }).map((s) => [s.id, s]))
  const problems = []
  for (const id of [...stories.keys()].sort()) {
    const story = stories.get(id)
    const entry = manifest[id]
    if (!entry) {
      problems.push({
        kind: 'missing-entry',
        id,
        detail: `the built index lists ${id} (${importFile(story)}) but the manifest has no entry for it`,
      })
      continue
    }
    if (entry.importPath !== story.importPath) {
      problems.push({
        kind: 'import-path',
        id,
        detail: `importPath is ${JSON.stringify(entry.importPath)}, the index says ${JSON.stringify(story.importPath)}`,
      })
    }
    if (entry.exportName !== story.exportName) {
      problems.push({
        kind: 'export-name',
        id,
        detail: `exportName is ${JSON.stringify(entry.exportName)}, the index says ${JSON.stringify(story.exportName)}`,
      })
    }
  }
  for (const id of Object.keys(manifest).sort()) {
    if (!stories.has(id)) {
      problems.push({
        kind: 'extra-entry',
        id,
        detail: `the manifest has an entry for ${id} but the built index lists no such story`,
      })
    }
  }
  return problems
}

// Structural equality of two JSON values (key order irrelevant).
export function sameJson(a, b) {
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b))
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    )
  }
  return value
}

// The entries a pass produced against the committed ones, for exactly the ids it ran (a selection
// narrower than the whole index checks only its own entries). One difference per id, in id order:
// `{ id, committed, fresh }` — `committed` is `undefined` for an id the manifest has no entry for.
export function findEntryDifferences({ manifest, fresh }) {
  return Object.keys(fresh)
    .sort()
    .filter((id) => !sameJson(manifest[id], fresh[id]))
    .map((id) => ({ id, committed: manifest[id], fresh: fresh[id] }))
}

// The manifest after a pass: every entry the pass produced replaces its committed one, and an entry
// for a story the index no longer lists is dropped (a removed or renamed story needs no browser to
// be recognised as gone). Keys end up in id order. An index story with no entry and not in `fresh`
// stays missing — `findKeyProblems` is what reports that.
export function mergeManifest({ manifest, fresh, index }) {
  const ids = new Set(listStories(index, { includeFixtures: true }).map((s) => s.id))
  const merged = {}
  for (const id of [...new Set([...Object.keys(manifest), ...Object.keys(fresh)])].sort()) {
    if (!ids.has(id)) continue
    merged[id] = fresh[id] ?? manifest[id]
  }
  return merged
}

// Text for the manifest file: each entry's per-width records on one line apiece before prettier
// (which keeps a record on one line when it fits and breaks it when it does not), so the file stays a
// reviewable size. Any text JSON.parse reads back to the same value, so check mode never depends on
// formatting.
export function serializeManifest(manifest) {
  const lines = ['{']
  const ids = Object.keys(manifest)
  ids.forEach((id, i) => {
    const entry = manifest[id]
    lines.push(`${JSON.stringify(id)}: {`)
    lines.push(`"importPath": ${JSON.stringify(entry.importPath)},`)
    lines.push(`"exportName": ${JSON.stringify(entry.exportName)},`)
    lines.push('"widths": {')
    const widths = Object.keys(entry.widths)
    widths.forEach((width, j) => {
      lines.push(
        `${JSON.stringify(width)}: ${JSON.stringify(entry.widths[width])}${j < widths.length - 1 ? ',' : ''}`,
      )
    })
    lines.push('}')
    lines.push(`}${i < ids.length - 1 ? ',' : ''}`)
  })
  lines.push('}')
  return `${lines.join('\n')}\n`
}

// The text above through this repository's own prettier (via stdin, the way
// `scripts/checks/state-coverage.mjs` formats its region), so the committed file is exactly what
// `pnpm format:check` expects.
export function formatManifest(text) {
  const result = spawnSync(
    'pnpm',
    ['exec', 'prettier', '--stdin-filepath', path.join(rootDir, MANIFEST_PATH)],
    { cwd: rootDir, input: text, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 },
  )
  if (result.status !== 0) {
    throw new Error(`prettier failed formatting the manifest: ${result.stderr || result.error}`)
  }
  return result.stdout
}

// A human line per problem or difference, ending with the command that fixes it.
export function describeKeyProblems(problems) {
  return [
    ...problems.map((p) => `  - ${p.id}: ${p.detail}`),
    `rewrite with \`${REWRITE_COMMAND}\` (add \`--changed\` to rewrite only the stories the diff selects).`,
  ]
}

export function describeEntryDifferences(differences) {
  return [
    ...differences.map((d) =>
      d.committed === undefined
        ? `  - ${d.id}: no committed entry; the browser rendered ${JSON.stringify(d.fresh.widths)}`
        : `  - ${d.id}: committed ${JSON.stringify(d.committed.widths)}\n      browser   ${JSON.stringify(d.fresh.widths)}`,
    ),
    `rewrite with \`${REWRITE_COMMAND}\` (add \`--changed\` to rewrite only the stories the diff selects).`,
  ]
}
