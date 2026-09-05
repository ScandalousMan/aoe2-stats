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
import { existsSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
// `.cjs`, not `.mjs` — see that file's header comment for why: Node's ESM loader can import a
// CommonJS module directly (`cjs-module-lexer` statically finds these named exports), which is the
// only shape this shared module can take without also being ambiguous to Playwright's transpile of
// `tests/visual/stories.spec.ts`, the module's other consumer.
import { resetResultsDir, checkStaleness } from './a11y-scan.cjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const storybookStaticDir = path.join(designSystemDir, 'storybook-static')
const indexPath = path.join(storybookStaticDir, 'index.json')

// The two axes every selected story is captured across. Order matters only for log readability —
// `stories.spec.ts` treats every unit independently.
const THEMES = ['light', 'dark']
const WIDTHS = [375, 768, 1280]

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
      // `entry.importPath`, e.g. `src/components/Button`), so a change to the component's
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
    result = spawnSync('pnpm', ['exec', 'playwright', 'test', '--config=playwright.config.ts'], {
      cwd: rootDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        VISUAL_STORIES_FILE: storiesPath,
      },
    })
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

main()
