#!/usr/bin/env node
// The runtime pass's entry point (T693 piece 3 and 4) — one command for CI and for a human.
//
//   node scripts/visual/state-coverage-runtime.mjs --keys
//       browserless: the manifest's keys are exactly the story ids the built index lists, and each
//       entry's `importPath` and `exportName` agree with it (set equality, as
//       `scripts/checks/story-baselines.mjs` does for baselines). Runs on every pull request.
//   node scripts/visual/state-coverage-runtime.mjs [--changed|--plants]
//       check mode: runs the pass in a real browser over the selected stories and fails on any
//       difference from the committed manifest.
//   node scripts/visual/state-coverage-runtime.mjs --write [--changed|--plants]
//       the same pass, then rewrites the selected entries (and drops entries for stories the index no
//       longer lists). A line shift in one component rewrites only the entries of the stories that
//       component affects.
//
// Selection: every story of the built index (fixtures included — a plant's entry is the point), or
// `--plants` (the fixture stories alone), or `--changed`: the union, for check and for write alike, of
//   (a) what `pnpm test:visual --changed` selects (`scripts/visual/story-selection.mjs`): a story's own
//       directory, or a global-reach path;
//   (b) every story whose committed entry cites, anywhere, a stamp whose file is in the diff;
//   (c) every story whose committed entry mounts or is placed by a tracked primitive whose directory
//       has a file in the diff;
//   (d) every story whose committed entry differs from the manifest at the diff base (a manifest absent
//       there means every entry differs), so a pull request that edits the manifest by hand has
//       those entries re-checked in the browser.
// The rules live in `selectRuntimeStories` (`state-coverage-runtime-model.mjs`). What they cannot see
// and nightly can: a composite B changes an axis it passes to a primitive, and a screen A renders B.
// A's mounts change, but nothing in A's committed entry names B's file, so unless (a) reaches A that
// change waits for the nightly run over every entry.
//
// Refused in every mode, before any selection: a built index with no published story (a rewrite over
// it would empty the manifest).
//
// The pass itself is `tests/visual/state-coverage-runtime.spec.ts`, which this spawns. It needs a built
// Storybook; the stories to run and their widths travel to it as a file, the way
// `scripts/visual/run.mjs` hands `stories.spec.ts` its units. `STATE_COVERAGE_RUNTIME_INDEX` and
// `STATE_COVERAGE_RUNTIME_MANIFEST` name another index and manifest file (the tests use them);
// unset, they are the built Storybook's and the committed manifest.
//
// Exit: 0 when everything checked agrees (or the rewrite succeeded), 1 otherwise.
import { spawnSync } from 'node:child_process'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { BUILD_STORYBOOK_COMMAND } from './missing-index.mjs'
import { REVIEW_WIDTHS } from './review-widths.mjs'
import {
  MANIFEST_PATH,
  buildEntry,
  describeEntryDifferences,
  describeKeyProblems,
  findEntryDifferences,
  findIndexProblem,
  findKeyProblems,
  formatManifest,
  manifestNeedsWrite,
  mergeManifest,
  selectRuntimeStories,
  serializeManifest,
} from './state-coverage-runtime-model.mjs'
import { isFixtureEntry, listStories } from './story-index.mjs'
import { changedFiles, fileAtBase } from './story-selection.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const indexPath =
  process.env.STATE_COVERAGE_RUNTIME_INDEX ??
  path.join(rootDir, 'packages', 'design-system', 'storybook-static', 'index.json')
const manifestPath =
  process.env.STATE_COVERAGE_RUNTIME_MANIFEST ?? path.join(rootDir, MANIFEST_PATH)
// How a `--changed` refusal speaks: this tool's own prefix and way out, never `run.mjs`'s.
const VOICE = { prefix: 'state-coverage-runtime', unscopedCommand: 'the pass without `--changed`' }
const SPEC = 'tests/visual/state-coverage-runtime.spec.ts'

function log(message) {
  console.log(`state-coverage-runtime: ${message}`)
}

function readManifest() {
  return existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : {}
}

function main() {
  const args = new Set(process.argv.slice(2))
  const keysOnly = args.has('--keys')
  const write = args.has('--write')
  const changedOnly = args.has('--changed')
  const plantsOnly = args.has('--plants')
  if (changedOnly && plantsOnly) {
    log('--changed and --plants are two selections; name one.')
    process.exit(1)
  }

  if (!existsSync(indexPath)) {
    log(
      `no Storybook build at ${path.relative(rootDir, indexPath)} — run \`${BUILD_STORYBOOK_COMMAND}\` first.`,
    )
    process.exit(1)
  }
  const index = JSON.parse(readFileSync(indexPath, 'utf8'))
  const indexProblem = findIndexProblem(index)
  if (indexProblem) {
    log(indexProblem)
    process.exit(1)
  }
  const manifest = readManifest()

  if (keysOnly) {
    const problems = findKeyProblems({ manifest, index })
    const stories = listStories(index, { includeFixtures: true })
    if (problems.length > 0) {
      log(`${problems.length} disagreement(s) between the manifest and the built index:`)
      for (const line of describeKeyProblems(problems)) console.log(line)
      process.exit(1)
    }
    log(
      `${Object.keys(manifest).length} manifest entries are exactly the ${stories.length} stories ` +
        `the built index lists (${stories.filter(isFixtureEntry).length} of them plants), importPath and exportName agreeing.`,
    )
    return
  }

  const all = listStories(index, { includeFixtures: true })
  const fixtureIds = all.filter(isFixtureEntry).map((s) => s.id)
  const selection = plantsOnly ? 'plants' : changedOnly ? 'changed' : 'all'
  let selected = all
  if (plantsOnly) selected = all.filter(isFixtureEntry)
  if (changedOnly) {
    const baseText = fileAtBase(MANIFEST_PATH, VOICE)
    const picked = selectRuntimeStories({
      stories: all,
      manifest,
      baseManifest: baseText === null ? null : JSON.parse(baseText),
      diff: changedFiles(VOICE),
    })
    selected = picked.stories
    const byRule = {}
    for (const why of picked.rules.values()) {
      for (const rule of why) byRule[rule] = (byRule[rule] ?? 0) + 1
    }
    log(`--changed selects ${selected.length} of ${all.length} (${JSON.stringify(byRule)}).`)
  }
  if (selected.length === 0) {
    log('nothing selected — nothing to run.')
    if (write) writeManifest(mergeManifest({ manifest, fresh: {}, index }), manifest)
    return
  }
  log(
    `running ${selected.length} stor${selected.length === 1 ? 'y' : 'ies'} x ${REVIEW_WIDTHS.length} widths (light theme).`,
  )

  const tmpDir = mkdtempSync(path.join(tmpdir(), 'aoe2-state-coverage-runtime-'))
  const workPath = path.join(tmpDir, 'work.json')
  const outDir = path.join(rootDir, 'test-results', 'state-coverage-runtime', 'raw')
  rmSync(outDir, { recursive: true, force: true })
  mkdirSync(outDir, { recursive: true })
  writeFileSync(
    workPath,
    JSON.stringify({
      stories: selected.map((s) => ({ id: s.id, widths: REVIEW_WIDTHS })),
      fixtureIds,
    }),
  )

  let result
  try {
    result = spawnSync(
      'pnpm',
      ['exec', 'playwright', 'test', SPEC, '--config=playwright.config.ts', '--reporter=dot'],
      {
        cwd: rootDir,
        stdio: 'inherit',
        env: { ...process.env, VISUAL_RUNTIME_FILE: workPath, VISUAL_RUNTIME_OUT_DIR: outDir },
      },
    )
  } finally {
    rmSync(tmpDir, { recursive: true, force: true })
  }
  if (result.error) {
    log(`could not start \`pnpm exec playwright test\`: ${result.error.message}`)
    process.exit(1)
  }

  const fresh = {}
  const failures = []
  for (const story of selected) {
    const file = path.join(outDir, `${story.id}.json`)
    if (!existsSync(file)) {
      failures.push(`${story.id}: the pass wrote no record`)
      continue
    }
    const raw = JSON.parse(readFileSync(file, 'utf8'))
    if (raw.error) failures.push(`${story.id}: ${raw.error.split('\n')[0]}`)
    else fresh[story.id] = buildEntry(story, raw.widths)
  }
  if (failures.length > 0 || result.status !== 0) {
    log(
      `${failures.length} stor${failures.length === 1 ? 'y' : 'ies'} the pass could not record (Playwright exit ${result.status}):`,
    )
    for (const f of failures) console.log(`  - ${f}`)
    process.exit(1)
  }

  if (write) {
    writeManifest(mergeManifest({ manifest, fresh, index }), manifest)
    log(
      `rewrote ${Object.keys(fresh).length} entr${Object.keys(fresh).length === 1 ? 'y' : 'ies'} in ${MANIFEST_PATH}.`,
    )
    return
  }

  const differences = findEntryDifferences({ manifest, fresh })
  if (differences.length > 0) {
    log(
      `${differences.length} of ${Object.keys(fresh).length} entr${differences.length === 1 ? 'y differs' : 'ies differ'} from ${MANIFEST_PATH}:`,
    )
    for (const line of describeEntryDifferences(differences, selection)) console.log(line)
    process.exit(1)
  }
  log(
    `${Object.keys(fresh).length} entr${Object.keys(fresh).length === 1 ? 'y' : 'ies'} match ${MANIFEST_PATH}.`,
  )
}

function writeManifest(merged, previous) {
  // Whatever this writes, the rewrite must leave `--keys` green for the stories it knows about. An
  // empty selection over a non-empty index leaves the file byte-identical.
  if (!manifestNeedsWrite(merged, previous, existsSync(manifestPath))) return
  writeFileSync(manifestPath, formatManifest(serializeManifest(merged)))
}

main()
