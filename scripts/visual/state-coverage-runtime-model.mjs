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
// An entry also carries `files`: the sorted unique repository-rooted paths of every stamped source file
// that rendered an element in the story's document (portals included — a story renders alone in its
// page), unioned across widths. It is what `selectRuntimeStories` reads, and the whole of what it
// reads: a diff selects the entries that recorded a file it touches.
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
import { importFile, isFixtureEntry, isFullPageEntry, listStories } from './story-index.mjs'
import { selectChangedStories } from './story-selection.mjs'

export const MANIFEST_PATH = 'packages/design-system/specs/state-coverage-runtime.json'
export const PASS_COMMAND = 'pnpm test:visual:state-coverage-runtime'
// The command that rewrites entries, named by every failure so the fix is never a guess.
export const REWRITE_COMMAND = `${PASS_COMMAND} --write`

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// One manifest entry for one index story, from what the browser recorded at each width. Each width's
// record may carry `files` (the stamped files that width rendered); they are unioned into the entry's
// own sorted `files` and kept out of the per-width records.
export function buildEntry(story, widthRecords) {
  const files = new Set()
  const widths = {}
  for (const [width, record] of Object.entries(widthRecords).sort(
    ([a], [b]) => Number(a) - Number(b),
  )) {
    const { files: rendered = [], ...rest } = record
    for (const file of rendered) files.add(file)
    widths[String(width)] = rest
  }
  return {
    importPath: story.importPath,
    exportName: story.exportName,
    files: [...files].sort(),
    widths,
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
    // The frame's full-page half is the built index's tag, the capture's own source, so it is checked
    // here without a browser (T703): a tag added or removed without a rewrite fails the keys. The clip
    // half is a browser's observation and only a pass can check it.
    const fullPage = isFullPageEntry(story)
    for (const [width, record] of Object.entries(entry.widths ?? {})) {
      if (record?.fullPage !== fullPage) {
        problems.push({
          kind: 'full-page',
          id,
          detail: `fullPage at ${width}px is ${JSON.stringify(record?.fullPage)}, the index ${fullPage ? 'tags' : 'does not tag'} the story \`visual-full-page\``,
        })
      }
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

// ---- The driver's refusals: arguments, a malformed manifest, a build without its plants -----------

export const FLAGS = ['--keys', '--write', '--changed', '--plants']

// The driver's arguments, each one a flag it knows. An unknown token — a typo, a positional word, two
// flags joined in one argument (`"--write --plants"`, which a shell quoting slip makes) — is a problem
// naming that exact token: ignoring it would run a different mode than the one asked for, and a
// `--write` that silently became a check (or the reverse) is the failure this exists to end.
export function parseArgs(argv) {
  const flags = new Set()
  const problems = []
  for (const token of argv) {
    if (FLAGS.includes(token)) flags.add(token)
    else {
      problems.push(
        `unknown argument ${JSON.stringify(token)} — the flags are ${FLAGS.join(', ')}, one per argument.`,
      )
    }
  }
  if (flags.has('--keys') && flags.size > 1) {
    problems.push(
      '--keys is the browserless key check and stands alone; it writes and selects nothing.',
    )
  }
  if (flags.has('--changed') && flags.has('--plants')) {
    problems.push('--changed and --plants are two selections; name one.')
  }
  return { flags, problems }
}

// The manifest from its text: `{ manifest }`, or `{ problem }` naming `label` (the file, or the file
// at the diff base) and the command that rewrites it — never a raw `SyntaxError`. A conflicted file, an
// empty one and any JSON that is not an object are all problems.
export function parseManifest(text, { label }) {
  let value
  try {
    value = JSON.parse(text)
  } catch (error) {
    return {
      problem:
        `${label} is not valid JSON (${error.message.split('\n')[0]}) — a merge conflict or a hand ` +
        `edit. \`${REWRITE_COMMAND}\` (no other flag) rebuilds it from the built Storybook.`,
    }
  }
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return {
      problem:
        `${label} is not a JSON object of story entries. \`${REWRITE_COMMAND}\` (no other flag) ` +
        'rebuilds it from the built Storybook.',
    }
  }
  return { manifest: value }
}

// A build that lists published stories but not one plant has lost the fixtures glob (or its tag): a
// pass over it checks nothing a plant asserts, and `--write --plants` would drop every plant entry.
// Returns the refusal, or `null`. An index with no published story at all is `findIndexProblem`'s.
export function findFixtureProblem(index) {
  const all = listStories(index, { includeFixtures: true })
  if (all.length === 0 || all.some(isFixtureEntry)) return null
  return (
    'the built Storybook lists no fixture story (tag `state-coverage-fixture`) — the plants are not ' +
    'in this build, so a pass would assert none of them and a rewrite would drop every plant entry. ' +
    `Check the \`./fixtures/**\` glob in packages/design-system/.storybook/main.ts, then rebuild: \`${BUILD_STORYBOOK_COMMAND}\`.`
  )
}

// ---- Which entries a --changed run re-checks ------------------------------------------------------

// The stories a diff leaves the runtime pass to re-check under `--changed`: the union of
//   (a) what `pnpm test:visual --changed` selects (`selectChangedStories`): a story's own directory, a
//       global-reach path, a file the preview reaches through module specifiers (T710: every story),
//       or (T707) a module the story file imports, transitively, through a module specifier — so a
//       clip, a tag or a force a story takes from another component's directory re-checks the story
//       when that module changes;
//   (b) every story whose committed entry RECORDED, in `files`, a source file the diff touches — the
//       stamped files that rendered an element in that story. Nothing else is read from the entry:
//       a stamp the entry cites and a primitive it mounts are both in `files`, because the element
//       carrying the stamp, and the primitive's own elements, are what put a file there. A test file,
//       a story file and a docs file are never stamped, so a diff on one of them alone selects
//       nothing through (b);
//   (d) every story whose committed entry differs from the one in the diff base's manifest
//       (`baseManifest`; `null` when the manifest does not exist there, so every entry differs) — a
//       pull request that edits the manifest alone has those entries checked in the browser.
// Returns `{ stories, rules }`: the stories in input order, and for each id the rules that selected it
// (`story-files`, `files`, `manifest-entry`).
//
// A file named by a specifier is selected by (a) whether or not it renders a stamped element in the
// story's SETTLED state (`files` is recorded once the story has settled, after `play()`): a hook, a
// `lib` helper, a component whose elements a `play()` removes (the idle state of
// `composite-uploadcontrol--real-selection-then-success` renders `Button` and the play clicks it away,
// so the entry records UploadControl and Callout only, but its component imports `Button`).
// Known shapes that nothing here selects, and nightly (which checks every entry) does; not an
// exhaustive list: a file a story reaches only at run time and not through a module specifier its
// story file or a reached file names (a hook's side effect, state a module sets that a story reads
// without importing it, a stylesheet's own `@import`, a `new URL('…', import.meta.url)` reach, a file a
// plugin or the bundler configuration injects).
export function selectRuntimeStories({ stories, manifest, baseManifest, diff }) {
  const diffFiles = new Set(diff)
  const byDiff = new Set(selectChangedStories(stories, diff).stories.map((s) => s.id))

  const rules = new Map()
  const picked = []
  for (const story of stories) {
    const entry = manifest[story.id]
    const why = []
    if (byDiff.has(story.id)) why.push('story-files')
    if ((entry?.files ?? []).some((file) => diffFiles.has(file))) why.push('files')
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
    lines.push(`"files": ${JSON.stringify(entry.files ?? [])},`)
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
