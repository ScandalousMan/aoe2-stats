#!/usr/bin/env node
// Diff-scoped visual regression runner for `pnpm test:visual` (T005, constitution VII).
//
// `pnpm test:visual`            -> every story in the built Storybook, in the full matrix below
//                                  (nightly full coverage).
// `pnpm test:visual --changed`  -> only the stories the diff *affects* (see the `changedOnly`
//                                  branch below), each still run through the full matrix
//                                  (pull-request runs — CI is a court, not a factory).
//
// T504 (FR-060, FR-061, SC-006): the suite is scoped by *story*, never by axis. Every selected
// story is expanded here into up to 6 capture units — {light, dark} x {375, 768, 1280} — and there
// is deliberately no flag, env var or CLI switch that narrows that expansion. A debugging need is
// not an exception: FR-061 forbids a narrower pull-request run outright, so no escape hatch is
// added "just for local iteration" either.
//
// Two things short-circuit before Playwright, and neither is an error: no Storybook build yet
// (packages/design-system doesn't exist until T003/T016), and --changed finding no touched story.
// Both print a message and exit 0, mirroring how pytest tolerates a missing testpaths entry.
//
// A third thing looks similar and is NOT one of these two: `--changed` unable to resolve its diff
// base at all (VISUAL_BASE_REF, default `origin/main` — see changedFiles() below). That is not
// "nothing changed", it is "the changed set is unknown", and reporting it as the former is exactly
// how this runner passed vacuously on every pull request for a stretch (CI's shallow, depth-1
// checkout left `origin/main` unresolvable, `runGit()` swallowed the failed `git diff` and returned
// `[]`, and an empty diff and an unreadable one printed the identical "nothing to test" — see
// `runGitOrFail()`, which exists to keep those two outcomes from ever looking the same again).
import {
  existsSync,
  readFileSync,
  readdirSync,
  writeFileSync,
  mkdtempSync,
  mkdirSync,
  rmSync,
} from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
// T675 (slice 2/N): the package-wide comparator-blind-spot sweep's own self-pairing and
// classification — this file's own `--state-signal-sweep` flow is the one caller, so the ESM
// import (never a `.cjs` bridge — nothing here is transpiled by Playwright, unlike
// `stories.spec.ts`'s own consumers) works directly.
import {
  discoverStoryFiles,
  extractFileStoryStates,
  planSelfRest,
  classifyBucket,
} from './state-signal-model.mjs'
// `.cjs`, not `.mjs` — see that file's header comment for why: Node's ESM loader can import a
// CommonJS module directly (`cjs-module-lexer` statically finds these named exports), which is the
// only shape this shared module can take without also being ambiguous to Playwright's transpile of
// `tests/visual/stories.spec.ts`, the module's other consumer.
import { resetResultsDir, checkStaleness } from './a11y-scan.cjs'
import { REVIEW_WIDTHS } from './review-widths.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const storybookStaticDir = path.join(designSystemDir, 'storybook-static')
const indexPath = path.join(storybookStaticDir, 'index.json')

// The two axes every selected story is captured across. Order matters only for log readability —
// `stories.spec.ts` treats every unit independently.
const THEMES = ['light', 'dark']
// 375/768/1280 are declared as standing rule 7 in packages/design-system/specs/README.md (closes
// DS-5, T529) — that rule is this array's source, not a value this file decides on its own.
// `review-widths.mjs` is the one place the literal itself lives in code (T529's design, low
// remediation finding — see that module's own comment).
const WIDTHS = REVIEW_WIDTHS

// Paths whose diff repaints or can repaint *every* story, so touching any of them selects the
// full story set rather than only the stories under the touched directory. Relative to the repo
// root, matching how `changedFiles()` reports paths.
const GLOBAL_REACH_PREFIXES = [
  'packages/design-system/tokens/',
  'packages/design-system/.storybook/',
  'packages/design-system/src/lib/',
  'packages/design-system/src/index.ts',
  'tests/visual/',
  'scripts/visual/',
]

const changedOnly = process.argv.slice(2).includes('--changed')
// T675 (slice 1/N): a report, never part of the ordinary `pnpm test:visual` / `--changed` selection
// below — its own entry point, `pnpm exec node scripts/visual/run.mjs --state-signal-sweep` (see
// `package.json`'s `test:visual:state-signal-sweep` script). Checked ahead of everything else in
// `main()` so this flow never touches the ordinary story-selection logic at all.
const stateSignalSweep = process.argv.slice(2).includes('--state-signal-sweep')

// Every ordinary visual spec under `tests/visual/` *except* the sweep's own — computed from the
// directory itself, not a hand-maintained list, so a future ordinary suite never needs this file
// edited to be included, and the sweep spec (deliberately excluded, see its own header) never needs
// this file edited to stay excluded either. Passed as explicit positional arguments to `playwright
// test` below: the previous, argument-less invocation relied on Playwright's own default
// `testMatch` picking up every `*.spec.ts` under `testDir` (`playwright.config.ts`), which would
// have silently swept `state-signal-sweep.spec.ts` into every ordinary run and every PR `visual`
// job the moment it existed as a sibling file.
const STATE_SIGNAL_SWEEP_SPEC = 'tests/visual/state-signal-sweep.spec.ts'
function listOrdinaryVisualSpecFiles() {
  const visualDir = path.join(rootDir, 'tests', 'visual')
  return readdirSync(visualDir)
    .filter((f) => f.endsWith('.spec.ts'))
    .map((f) => path.posix.join('tests/visual', f))
    .filter((f) => f !== STATE_SIGNAL_SWEEP_SPEC)
    .sort()
}

function log(message) {
  console.log(`test:visual: ${message}`)
}

function runGit(args) {
  const result = spawnSync('git', args, { cwd: rootDir, encoding: 'utf8' })
  if (result.status !== 0) return []
  return result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

// Same shape as runGit(), except a failed invocation is fatal rather than swallowed into `[]`.
// Reserved for the one diff whose base is a name that might not resolve in this checkout at all
// (`${base}...HEAD` below) — as opposed to a diff against `HEAD` or a listing of untracked files,
// neither of which names anything that can fail to exist. Conflating "the command failed" with
// "the command found nothing" is the defect this exists to end: a shallow CI checkout with no
// `origin/main` locally available used to make every pull-request run silently select zero
// stories and exit 0, looking identical to a docs-only change that genuinely touches none.
function runGitOrFail(args, baseDescription) {
  const result = spawnSync('git', args, { cwd: rootDir, encoding: 'utf8' })
  if (result.status !== 0) {
    const stderr = (result.stderr ?? '').trim()
    log(
      `--changed could not resolve its diff base, ${baseDescription} (\`git ${args.join(' ')}\`)` +
        (stderr ? ` — ${stderr}` : '') +
        '. This is not "nothing changed" — it is "the changed set is unknown" — so refusing to ' +
        'report zero affected stories. Set VISUAL_BASE_REF to a ref this checkout can resolve ' +
        '(a commit SHA already fetched, or a branch after `git fetch` has brought it in), or run ' +
        'the full, unscoped `pnpm test:visual` instead.',
    )
    process.exit(1)
  }
  return result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

// Every file that differs from the diff base, plus anything uncommitted or untracked, so a run
// before *and* after `git add` behaves the same way for a developer working locally.
function changedFiles() {
  const base = process.env.VISUAL_BASE_REF ?? 'origin/main'
  const files = new Set()
  for (const f of runGitOrFail(['diff', '--name-only', `${base}...HEAD`], `"${base}"`)) files.add(f)
  for (const f of runGit(['diff', '--name-only', 'HEAD'])) files.add(f)
  for (const f of runGit(['ls-files', '--others', '--exclude-standard'])) files.add(f)
  return [...files]
}

const storyGlob = /\.stories\.[jt]sx?$/

function main() {
  if (!existsSync(indexPath)) {
    log(
      'no Storybook build found at packages/design-system/storybook-static/index.json — nothing ' +
        'to test. Run `pnpm --filter design-system build-storybook` first if stories already exist.',
    )
    process.exit(0)
  }

  if (stateSignalSweep) {
    runStateSignalSweep()
    return
  }

  const index = JSON.parse(readFileSync(indexPath, 'utf8'))
  const entries = Object.values(index.entries ?? index.stories ?? {})
  let stories = entries.filter((entry) => entry.type === undefined || entry.type === 'story')

  if (stories.length === 0) {
    log('Storybook build has no stories — nothing to test.')
    process.exit(0)
  }

  if (changedOnly) {
    const diff = changedFiles()

    // A change under any of these paths repaints (or can repaint) every story — a token, the
    // preview decorator, a shared `lib` helper, the public surface, or the harness itself — so it
    // selects the full story set rather than narrowing to a directory. Without this, a change to
    // `packages/design-system/tokens/color.json` would touch no `.stories.tsx` file and select
    // zero stories, which is exactly the gap FR-060/FR-061 exist to close: an "affected" story is
    // one whose *rendered output* the diff can change, not only one whose own file was edited.
    const globallyAffected = diff.some((f) =>
      GLOBAL_REACH_PREFIXES.some((prefix) => f.startsWith(prefix)),
    )

    if (!globallyAffected) {
      // Directory of each story's own file, relative to the design-system package (matching
      // `entry.importPath`, e.g. `src/primitives/Button`), so a change to the component's
      // implementation file — not only to its `.stories.tsx` — selects the story too.
      const touchedInPackage = diff
        .filter((f) => f.startsWith('packages/design-system/'))
        .map((f) => path.relative(designSystemDir, path.join(rootDir, f)).split(path.sep).join('/'))
      const touchedDesignSystemDirs = new Set(touchedInPackage.map((f) => path.posix.dirname(f)))
      const touchedStoryFiles = new Set(touchedInPackage.filter((f) => storyGlob.test(f)))

      stories = stories.filter((entry) => {
        const importPath = (entry.importPath ?? '').replace(/^\.\//, '')
        if (touchedStoryFiles.has(importPath)) return true
        return touchedDesignSystemDirs.has(path.posix.dirname(importPath))
      })

      if (stories.length === 0) {
        log('--changed: nothing in the diff affects a story — nothing to test.')
        process.exit(0)
      }
    }
  }

  // Every selected story is expanded into one capture unit per {theme, width} pair — the full
  // matrix, always, with no flag anywhere that narrows it (FR-061). `stories.spec.ts` stays dumb:
  // it renders exactly the units listed here and never re-derives which axes apply to which story.
  const units = stories.flatMap((entry) =>
    THEMES.flatMap((theme) =>
      WIDTHS.map((width) => ({
        id: entry.id,
        theme,
        width,
        // A story tagged `visual-full-page` names a subject that escapes the `#storybook-root`
        // box — a `position: fixed` dialog (fixed positioning is relative to the viewport, not
        // any ancestor box) or a popover that overflows its trigger's layout box (an absolutely
        // positioned descendant does not enlarge that box, so a screenshot clipped to it never
        // reaches the popover at all). Screenshotting the whole page instead of just the root
        // element is the only way those baselines see the thing they are named for.
        fullPage: (entry.tags ?? []).includes('visual-full-page'),
      })),
    ),
  )

  log(
    `running ${stories.length} stor${stories.length === 1 ? 'y' : 'ies'}` +
      (changedOnly ? ' (diff-scoped)' : ' (full run)') +
      ` across ${THEMES.length} themes x ${WIDTHS.length} widths = ${units.length} capture units.`,
  )

  // T507: cleared here, once per invocation, rather than by a test — `stories.spec.ts`'s axe scan
  // (once per story-theme pair, at its designated width) appends to these files from whichever
  // worker ran it, and a leftover file from an earlier, differently-scoped invocation would make a
  // component this run never reselected look "covered", corrupting the staleness check below.
  resetResultsDir()

  // The selected units used to travel to Playwright as inline JSON in `VISUAL_STORIES`. Linux
  // caps a single argv/envp string at `MAX_ARG_STRLEN` (128 KiB), independent of and far tighter
  // than the combined `ARG_MAX` the whole process's argv+environ share; the full, unscoped
  // matrix's JSON is ~166 KB and crosses that ceiling on its own, so `spawnSync` below failed with
  // `E2BIG` before Playwright ever started (confirmed on CI, run 33971176171). Writing the payload
  // to a temp file and passing only its path removes the ceiling entirely — a path is a few dozen
  // bytes regardless of how many units it names.
  //
  // `mkdtempSync(tmpdir())`, not `RUNNER_TEMP`: this script also runs on a developer machine
  // (`pnpm test:visual` / `--changed`), where `RUNNER_TEMP` does not exist at all, so branching on
  // it would need a fallback anyway. `tmpdir()` (Node's own cross-platform temp directory, `/tmp`
  // on the `ubuntu-latest` runner this workflow uses) needs none: the runner's job container is
  // torn down at the end of every job regardless, so there is no accumulation risk to design
  // around, and `finally` below removes the directory immediately in the common case besides.
  const tmpDir = mkdtempSync(path.join(tmpdir(), 'aoe2-visual-stories-'))
  const storiesPath = path.join(tmpDir, 'stories.json')
  writeFileSync(storiesPath, JSON.stringify(units))

  let result
  try {
    result = spawnSync(
      'pnpm',
      [
        'exec',
        'playwright',
        'test',
        ...listOrdinaryVisualSpecFiles(),
        '--config=playwright.config.ts',
      ],
      {
        cwd: rootDir,
        stdio: 'inherit',
        env: {
          ...process.env,
          VISUAL_STORIES_FILE: storiesPath,
        },
      },
    )
  } finally {
    // Cleaned up here — a `finally` runs whether `spawnSync` above returned normally or threw —
    // rather than left for the OS's own temp-directory reaping, so a developer running this
    // repeatedly does not accumulate one leftover directory per invocation.
    rmSync(tmpDir, { recursive: true, force: true })
  }

  // spawnSync() reports a spawn-level failure (the executable never ran at all — not "ran and
  // exited non-zero") through `result.error`, not `result.status`, which stays `null` in that
  // case. `result.status ?? 1` below turns that into a plain exit code with nothing printed —
  // the same shape of silence `runGitOrFail()` exists to end for `git`, and worth naming here
  // too: `stdio: 'inherit'` means Playwright's own output would normally explain a real test
  // failure, so an exit with none is spawnSync itself refusing the call.
  if (result.error) {
    log(`could not start \`pnpm exec playwright test\`: ${result.error.message}`)
  }

  // T507's staleness check: an `a11y-allowlist.json` entry naming a component-and-rule pair this
  // run scanned and did not report is a stale suppression hiding a fix that already happened.
  // Checked here, after Playwright exits, because the scan's own results — written across however
  // many workers ran it — only exist once the whole run has finished; a per-test check would see
  // only its own worker's slice. This runs regardless of Playwright's own exit status, so a stale
  // entry is reported even on an otherwise-green run.
  const stale = checkStaleness()
  if (stale.length > 0) {
    log(
      `${stale.length} stale scripts/visual/a11y-allowlist.json entr${stale.length === 1 ? 'y' : 'ies'}:`,
    )
    for (const entry of stale) {
      log(
        `  - ${entry.component} / ${entry.rule} — scanned this run, not reported; fix owed: ` +
          `${entry.fixOwed ?? '(undated)'}, fix by ${entry.fixBy ?? '(undated)'}`,
      )
    }
  }

  const exitCode = result.status ?? 1
  process.exit(stale.length > 0 ? 1 : exitCode)
}

// --- T675 (slice 2/N): package-wide comparator-blind-spot sweep --------------------------------

// Every state story in the tree (`state-signal-model.mjs`'s own `discoverStoryFiles` +
// `extractFileStoryStates`), self-paired against its own resting frame (`planSelfRest`) — split
// into `measurable` (a story `tests/visual/state-signal-sweep.spec.ts` will actually render twice)
// and `notMeasurable` (reported as-is, no rendering: `planSelfRest` itself already answers "not
// measurable" without a browser — see that function's own comment for the one static case this
// covers, unexercised by any real story in this tree today).
function buildStateSignalWork() {
  const measurable = []
  const notMeasurable = []
  for (const filePath of discoverStoryFiles()) {
    const source = readFileSync(filePath, 'utf8')
    let result
    try {
      result = extractFileStoryStates(filePath, source)
    } catch (err) {
      log(`state-signal-sweep: skipping ${path.relative(rootDir, filePath)}: ${err.message}`)
      continue
    }
    if (!result) continue
    const relFile = path.relative(rootDir, filePath)
    for (const story of result.stories) {
      if (!story.isStateStory) continue
      const plan = planSelfRest(story)
      if (plan.measurable) {
        measurable.push({
          stateId: story.id,
          exportName: story.exportName,
          mode: plan.mode,
          hasClip: story.clip !== null,
          file: relFile,
        })
      } else {
        notMeasurable.push({
          stateId: story.id,
          exportName: story.exportName,
          file: relFile,
          reason: plan.reason,
          detail: plan.detail,
        })
      }
    }
  }
  return { measurable, notMeasurable }
}

function formatPct(ratio) {
  return `${(ratio * 100).toFixed(3)}%`
}

const BUCKET_TITLES = {
  zero: 'Zero surviving pixels on every unit — no clip can help',
  'zero-despite-clip': 'Zero surviving pixels despite an existing clip — no clip can help',
  'clip-fixes': 'A real signal at or under 1% on at least one unit, unclipped — a clip fixes this',
  'clipped-still-under-threshold':
    'Already clipped, still at or under 1% — a clip that does not defend',
  defended: 'Defended (over 1% on every unit), already clipped',
  'defended-without-clip': 'Defended (over 1% on every unit), no clip involved',
  'dimension-mismatch':
    'State and rest render at different pixel dimensions — not a comparator question',
}
const BUCKET_ORDER = Object.keys(BUCKET_TITLES)

// Renders `test-results/state-signal-sweep/report.{json,md}` — a report, never restated into
// `packages/design-system/specs/README.md` beyond what classifying needs (this task's own
// instruction): the register row names each story and its bucket, not every per-unit ratio this
// file's own JSON already carries in full.
function writeStateSignalReport({ classified, notMeasurable, measurableCount }) {
  const reportDir = path.join(rootDir, 'test-results', 'state-signal-sweep')
  mkdirSync(reportDir, { recursive: true })
  writeFileSync(
    path.join(reportDir, 'report.json'),
    JSON.stringify({ classified, notMeasurable }, null, 2),
  )

  const byBucket = new Map()
  for (const c of classified) {
    if (!byBucket.has(c.bucket)) byBucket.set(c.bucket, [])
    byBucket.get(c.bucket).push(c)
  }

  const lines = []
  lines.push('# State-signal comparator sweep (T675, slice 2/N — self-paired)')
  lines.push('')
  lines.push(
    'Command: `node scripts/visual/run.mjs --state-signal-sweep` (rebuild Storybook first: ' +
      '`pnpm --filter design-system build-storybook`). Every story below is compared against ' +
      "*itself* (`state-signal-model.mjs`'s own `planSelfRest`, `tests/visual/" +
      "state-signal-sweep.spec.ts`'s own header) — the state and the rest share the same args, " +
      "render, viewport and clip by construction. Local renders differ from CI's by roughly 2% in " +
      'absolute terms, but every comparison below is two renders taken on the same machine, in the ' +
      'same run, against each other — valid for this classification.',
  )
  lines.push('')
  lines.push(
    `${measurableCount} of ${measurableCount + notMeasurable.length} state stor` +
      `${measurableCount + notMeasurable.length === 1 ? 'y' : 'ies'} measured; ` +
      `${notMeasurable.length} not measurable (see the table at the end).`,
  )
  lines.push('')

  for (const bucket of BUCKET_ORDER) {
    const entries = byBucket.get(bucket) ?? []
    if (entries.length === 0) continue
    lines.push(`## ${BUCKET_TITLES[bucket]} (${entries.length})`)
    lines.push('')
    lines.push('| State story | mode | min ratio | file |')
    lines.push('| --- | --- | --- | --- |')
    for (const e of [...entries].sort((a, b) => a.stateId.localeCompare(b.stateId))) {
      const ratio = typeof e.minRatio === 'number' ? formatPct(e.minRatio) : 'n/a'
      lines.push(`| \`${e.stateId}\` | ${e.mode} | ${ratio} | ${e.file} |`)
    }
    lines.push('')
  }

  if (notMeasurable.length > 0) {
    lines.push(`## Not measurable (${notMeasurable.length})`)
    lines.push('')
    lines.push('| State story | reason | detail | file |')
    lines.push('| --- | --- | --- | --- |')
    for (const e of [...notMeasurable].sort((a, b) => a.stateId.localeCompare(b.stateId))) {
      lines.push(`| \`${e.stateId}\` | ${e.reason} | ${e.detail} | ${e.file} |`)
    }
    lines.push('')
  }

  writeFileSync(path.join(reportDir, 'report.md'), `${lines.join('\n')}\n`)
  log(`state-signal-sweep: report written to test-results/state-signal-sweep/report.{json,md}`)
}

// Never part of `pnpm test:visual` / `--changed` (see `stateSignalSweep`'s own comment above): its
// own entry point only, `pnpm exec node scripts/visual/run.mjs --state-signal-sweep`
// (`package.json`'s `test:visual:state-signal-sweep`). Builds the work list from source alone (no
// browser), spawns Playwright against `state-signal-sweep.spec.ts` alone for the rendering half,
// then classifies whatever raw per-unit results that run produced — regardless of Playwright's own
// exit status, the same "a stale finding is still reported on an otherwise-green run" shape
// `checkStaleness()` above already follows, because one pair's own render failure (a selector this
// task's own render-time check throws on, `story-render.ts`'s own `locateClipPart`) says nothing
// about any other pair's numbers.
function runStateSignalSweep() {
  const { measurable, notMeasurable } = buildStateSignalWork()
  log(
    `state-signal-sweep: ${measurable.length} measurable pair(s), ${notMeasurable.length} ` +
      'not-measurable state stor(y/ies) found from source.',
  )

  const rawResultsDir = path.join(rootDir, 'test-results', 'state-signal-sweep', 'raw')
  rmSync(rawResultsDir, { recursive: true, force: true })
  mkdirSync(rawResultsDir, { recursive: true })

  const tmpDir = mkdtempSync(path.join(tmpdir(), 'aoe2-state-signal-sweep-'))
  const workItemsPath = path.join(tmpDir, 'work-items.json')
  writeFileSync(workItemsPath, JSON.stringify(measurable))

  let result
  try {
    result = spawnSync(
      'pnpm',
      ['exec', 'playwright', 'test', STATE_SIGNAL_SWEEP_SPEC, '--config=playwright.config.ts'],
      {
        cwd: rootDir,
        stdio: 'inherit',
        env: { ...process.env, VISUAL_STATE_SWEEP_FILE: workItemsPath },
      },
    )
  } finally {
    rmSync(tmpDir, { recursive: true, force: true })
  }

  if (result.error) {
    log(
      'could not start `pnpm exec playwright test` for the state-signal sweep: ' +
        result.error.message,
    )
    process.exit(1)
  }

  const hasClipByStateId = new Map(measurable.map((m) => [m.stateId, m.hasClip]))
  const rawFiles = existsSync(rawResultsDir) ? readdirSync(rawResultsDir) : []
  const classified = rawFiles.map((f) => {
    const entry = JSON.parse(readFileSync(path.join(rawResultsDir, f), 'utf8'))
    const hasClip = hasClipByStateId.get(entry.stateId) ?? false
    return { ...entry, ...classifyBucket({ hasClip, unitResults: entry.unitResults }) }
  })

  writeStateSignalReport({ classified, notMeasurable, measurableCount: measurable.length })

  process.exit(result.status ?? 1)
}

main()
