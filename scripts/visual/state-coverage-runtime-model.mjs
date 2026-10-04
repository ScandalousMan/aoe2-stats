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
//
// An instance is an object, `{ component, variant, size, disabledAt }` in that key order, so a reader
// (T694) decodes it in Node without reading `preview.tsx`: `variant` and `size` are `null` when the
// primitive has no such axis or no value was passed and there is no default; `disabledAt` is the
// sorted unique stamps of the host elements that instance's own file (or its `cloneElement` call)
// placed and the DOM reports disabled — empty when nothing disabled renders.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { BUILD_STORYBOOK_COMMAND } from './missing-index.mjs'
import { importFile, listStories } from './story-index.mjs'
import { selectChangedStories } from './story-selection.mjs'

export const MANIFEST_PATH = 'packages/design-system/specs/state-coverage-runtime.json'
export const PASS_COMMAND = 'pnpm test:visual:state-coverage-runtime'
// The command that rewrites entries, named by every failure so the fix is never a guess.
export const REWRITE_COMMAND = `${PASS_COMMAND} --write`

// The directory each tracked primitive's own source lives in — what `.storybook/preview.tsx`
// registers as `directory`, repeated here because this module runs in Node and cannot import a
// browser module. `state-coverage-runtime-model.test.mjs` fails when the two disagree.
export const TRACKED_DIRECTORIES = {
  Button: 'packages/design-system/src/primitives/Button/',
  Link: 'packages/design-system/src/primitives/Link/',
  Field: 'packages/design-system/src/primitives/Field/',
  Menu: 'packages/design-system/src/primitives/Menu/',
}

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

// A build with no published story cannot be recorded: merging a pass over it would drop every entry
// of the manifest. Returns the refusal, or `null` when the index lists at least one story.
export function findIndexProblem(index) {
  if (listStories(index).length > 0) return null
  return `Storybook build has no stories — nothing to record, and a rewrite would empty the manifest. Rebuild: \`${BUILD_STORYBOOK_COMMAND}\`.`
}

// ---- Which entries a --changed run re-checks ------------------------------------------------------

// Every tracked primitive instance an entry records, across widths: what it mounts, what placed its
// forced element, what placed its focused one.
export function entryInstances(entry) {
  const found = []
  for (const record of Object.values(entry?.widths ?? {})) {
    found.push(...(record.mounts ?? []))
    if (record.force?.placedBy) found.push(record.force.placedBy)
    if (record.focus?.placedBy) found.push(record.focus.placedBy)
  }
  return found
}

// Every stamp an entry cites, across widths: the forced element's, the focused element's, and each
// instance's `disabledAt`.
export function entryStamps(entry) {
  const stamps = new Set()
  for (const record of Object.values(entry?.widths ?? {})) {
    if (record.force?.stamp) stamps.add(record.force.stamp)
    if (record.focus?.stamp) stamps.add(record.focus.stamp)
  }
  for (const instance of entryInstances(entry)) {
    for (const stamp of instance.disabledAt ?? []) stamps.add(stamp)
  }
  return stamps
}

const stampFile = (stamp) => stamp.slice(0, stamp.lastIndexOf(':'))

// The stories a diff leaves the runtime pass to re-check under `--changed`: the union of
//   (a) what `pnpm test:visual --changed` selects (`selectChangedStories`, from the story's own
//       directory or a global-reach path) — a story's own file, or its component's;
//   (b) every story whose committed entry cites, anywhere, a stamp whose file is in the diff — the
//       entry is a record of that file's line numbers and a line shift changes it;
//   (c) every story whose committed entry mounts or is placed by a tracked primitive whose directory
//       has a file in the diff — what a primitive renders changes what the story mounts;
//   (d) every story whose committed entry differs from the one in the diff base's manifest
//       (`baseManifest`; `null` when the manifest does not exist there, so every entry differs) — a
//       pull request that edits the manifest alone has those entries checked in the browser.
// Returns `{ stories, rules }`: the stories in input order, and for each id the rules that selected it.
//
// What this cannot see, and nightly (which checks every entry) does: a composite B changes an axis it
// passes to a primitive and a screen A renders B. A's mounts change, but nothing in A's committed
// entry names B's file, so unless (a) reaches A the change waits for nightly.
export function selectRuntimeStories({ stories, manifest, baseManifest, diff }) {
  const diffFiles = new Set(diff)
  const touchedDirectories = Object.entries(TRACKED_DIRECTORIES)
    .filter(([, dir]) => diff.some((file) => file.startsWith(dir)))
    .map(([name]) => name)
  const byDiff = new Set(selectChangedStories(stories, diff).stories.map((s) => s.id))

  const rules = new Map()
  const picked = []
  for (const story of stories) {
    const entry = manifest[story.id]
    const why = []
    if (byDiff.has(story.id)) why.push('story-files')
    if ([...entryStamps(entry)].some((stamp) => diffFiles.has(stampFile(stamp)))) {
      why.push('cited-stamp')
    }
    if (entryInstances(entry).some((i) => touchedDirectories.includes(i.component))) {
      why.push('tracked-primitive')
    }
    const before = baseManifest === null ? undefined : baseManifest[story.id]
    if (entry !== undefined || before !== undefined) {
      if (baseManifest === null || !sameJson(entry, before)) why.push('manifest-entry')
    }
    if (why.length > 0) {
      rules.set(story.id, why)
      picked.push(story)
    }
  }
  return { stories: picked, rules }
}

// Whether a pass's merged manifest must be written: always when the file is missing, otherwise only
// when it is not the committed one — so an empty selection over a non-empty index leaves the file
// byte-identical.
export function manifestNeedsWrite(merged, previous, fileExists) {
  return !fileExists || JSON.stringify(merged) !== JSON.stringify(previous)
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

// The command that rewrites exactly the entries a failing run covered, so the fix is never a guess.
function rewriteHint(selection) {
  if (selection === 'plants') {
    return `rewrite with \`${REWRITE_COMMAND} --plants\` (the plants alone).`
  }
  if (selection === 'changed') {
    return `rewrite with \`${REWRITE_COMMAND} --changed\` (the stories the diff selects).`
  }
  return `rewrite with \`${REWRITE_COMMAND}\` (add \`--changed\` to rewrite only the stories the diff selects, or \`--plants\` for the plants alone).`
}

// A human line per problem or difference, ending with the command that fixes it. `selection` is the
// run that found them: `'plants'`, `'changed'`, or anything else for the whole index.
export function describeKeyProblems(problems) {
  return [...problems.map((p) => `  - ${p.id}: ${p.detail}`), rewriteHint('all')]
}

export function describeEntryDifferences(differences, selection = 'all') {
  return [
    ...differences.map((d) =>
      d.committed === undefined
        ? `  - ${d.id}: no committed entry; the browser rendered ${JSON.stringify(d.fresh.widths)}`
        : `  - ${d.id}: committed ${JSON.stringify(d.committed.widths)}\n      browser   ${JSON.stringify(d.fresh.widths)}`,
    ),
    rewriteHint(selection),
  ]
}
