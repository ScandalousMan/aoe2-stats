#!/usr/bin/env node
// T810 (feature 007, Story 2): the host's Ignored Build Step. `vercel.json`'s `ignoreCommand`
// runs this before a deployment builds. Exit 0 cancels the build, exit 1 builds. The contract is
// `specs/007-shrink-deployment-storage/contracts/build-skip-rule.md`; the decision order is
// `data-model.md` section 4, repeated in `decide` below step by step.
//
// Fail safe, always: every doubt builds. The module runs before any install, so it uses Node's
// standard library only, and it makes no network call: it never fetches, never deepens the clone,
// never asks the host's API. It reads three host variables and runs one local `git diff`.

import { execFileSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'

// --- The two lists ---------------------------------------------------------------------------
// Each pattern carries its one-line reason. The lists may overlap (`scripts/**` covers
// `scripts/deploy/**`); the always-deploy list is checked first, so an overlap cannot skip.
// Supported glob shapes: `<dir>/**`, a single-segment `*`, a leading `**/`.

/** Changes here always deploy, whatever else the push contains (FR-008). */
export const ALWAYS_DEPLOY = [
  ['infra/migrations/**', 'a migration changes the schema the functions run against'],
  ['**/pyproject.toml', 'dependency and build declarations of the Python bundle'],
  ['uv.lock', 'the lock decides what the function bundle installs'],
  ['**/package.json', 'dependency and script declarations of the web build'],
  ['pnpm-lock.yaml', 'the lock decides what the web build installs'],
  ['vercel.json', 'the host configuration, including this rule'],
  ['.vercelignore', 'decides what the host uploads'],
  ['.env.example', 'declares the configuration the deployment target must carry'],
  ['scripts/checks/config-preflight.mjs', 'runs inside the build command'],
  ['api/**', 'the three function entrypoints'],
  ['scripts/deploy/**', 'the skip rule itself and its list'],
]

/** Changes matched only by these (and by nothing in ALWAYS_DEPLOY) skip the build (FR-006). */
export const NEVER_SHIPPED = [
  ['docs/**', 'prose'],
  ['specs/**', 'spec-kit artifacts'],
  ['.specify/**', 'spec-kit artifacts'],
  ['.claude/**', 'agent configuration; neither the build nor a function reads it'],
  ['.github/**', 'CI workflows; neither the build nor a function reads them'],
  ['tests/**', 'root test suites, visual tests and fixtures'],
  ['apps/*/tests/**', 'per-package tests; the wheels package src/ only'],
  ['packages/*/tests/**', 'per-package tests; the wheels package src/ only'],
  [
    '**/*.test.ts',
    "test file; no JavaScript module imports it, and Tailwind's @source scan can add or drop CSS rules for classes only it names, which no shipped markup uses",
  ],
  [
    '**/*.test.tsx',
    "test file; no JavaScript module imports it, and Tailwind's @source scan can add or drop CSS rules for classes only it names, which no shipped markup uses",
  ],
  [
    '**/*.test.mjs',
    "test file; no JavaScript module imports it, and Tailwind's @source scan can add or drop CSS rules for classes only it names, which no shipped markup uses",
  ],
  [
    '**/*.stories.tsx',
    "story file; no JavaScript module imports it, and Tailwind's @source scan can add or drop CSS rules for classes only it names, which no shipped markup uses",
  ],
  ['packages/design-system/.storybook/**', 'Storybook configuration; apps/web does not import it'],
  ['packages/design-system/__screenshots__/**', 'visual baselines, already out of the upload'],
  ['packages/design-system/specs/**', 'design specs'],
  [
    'scripts/**',
    'development and CI tooling; the always-deploy list carves out its two exceptions',
  ],
  ['README.md', 'root prose'],
  ['CLAUDE.md', 'root prose'],
  ['playwright.config.ts', 'visual-test configuration'],
]

// --- Glob matching ---------------------------------------------------------------------------

/** Compile one repository-rooted glob into an anchored regular expression. */
export function globToRegExp(glob) {
  let source = ''
  let i = 0
  while (i < glob.length) {
    if (glob.startsWith('**/', i) && i === 0) {
      source += '(?:.*/)?'
      i += 3
    } else if (glob.startsWith('/**', i) && i + 3 === glob.length) {
      source += '/.+'
      i += 3
    } else if (glob[i] === '*') {
      if (glob[i + 1] === '*') throw new Error(`unsupported glob shape: ${glob}`)
      source += '[^/]*'
      i += 1
    } else {
      source += glob[i].replace(/[.+?^${}()|[\]\\]/g, '\\$&')
      i += 1
    }
  }
  return new RegExp(`^${source}$`)
}

function compile(list) {
  return list.map(([pattern]) => globToRegExp(pattern))
}

const ALWAYS_RES = compile(ALWAYS_DEPLOY)
const NEVER_RES = compile(NEVER_SHIPPED)

/** True when a change to `path` can reach a deployment (steps 4 and 5 of the decision). */
export function isShipped(path) {
  if (ALWAYS_RES.some((re) => re.test(path))) return true
  return !NEVER_RES.some((re) => re.test(path))
}

// --- The decision ----------------------------------------------------------------------------

/**
 * Pure decision. `changedPaths` is an array, or null when the diff could not be computed
 * (`unavailable` then says why). Returns `{ exit, line }`.
 */
export function decide({ environment, base, head, changedPaths, unavailable }) {
  // 1. Non-production -> skip (FR-011). An unreadable environment is not "not production".
  if (environment && environment !== 'production') {
    return { exit: 0, line: `skip: non-production (${environment})` }
  }
  // 2. Any input unreadable, or the diff failed -> build (FR-007).
  if (!environment) return { exit: 1, line: 'build: target environment unreadable' }
  if (!base) return { exit: 1, line: 'build: comparison base unreadable' }
  if (!head) return { exit: 1, line: 'build: pushed commit unreadable' }
  if (!Array.isArray(changedPaths)) {
    return { exit: 1, line: `build: ${unavailable || 'changed paths unavailable'}` }
  }
  // 3. No changed path at all: the base is the pushed commit, a redeploy -> build (FR-010).
  if (changedPaths.length === 0) {
    return { exit: 1, line: `build: no changed path (${base}..${head})` }
  }
  // 4. + 5. A path on the always-deploy list, or matched by no never-shipped pattern -> build.
  const shipped = changedPaths.find(isShipped)
  if (shipped !== undefined) {
    return { exit: 1, line: `build: ${shipped} (${base}..${head})` }
  }
  // 6. Otherwise skip.
  return {
    exit: 0,
    line: `skip: nothing shipped between ${base} and ${head} (${changedPaths.length} paths)`,
  }
}

// --- The entry -------------------------------------------------------------------------------

const COMMIT_ID = /^[0-9a-f]{7,64}$/i

/** A hanging git must throw so the catches below build (FR-007), not leave the outcome to the host. */
export const GIT_TIMEOUT_MS = 30_000

/** One local git call, bounded by `timeoutMs`; the commit checks and the diff all go through it. */
export function runGit(args, { cwd, timeoutMs = GIT_TIMEOUT_MS } = {}) {
  return execFileSync('git', args, {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
    timeout: timeoutMs,
  })
}

/**
 * Read the three host variables, check the base is in the clone, run one local `git diff`.
 * `git` is injectable so the test can make it fail. Never throws; never returns exit 0 on error.
 */
export function run(env, { cwd = process.cwd(), git = runGit } = {}) {
  try {
    const environment = (env.VERCEL_ENV ?? '').trim()
    const head = (env.VERCEL_GIT_COMMIT_SHA ?? '').trim()
    const base = (env.VERCEL_GIT_PREVIOUS_SHA ?? '').trim()
    let changedPaths = null
    let unavailable = null
    if (environment === 'production' && COMMIT_ID.test(base) && COMMIT_ID.test(head)) {
      try {
        git(['cat-file', '-e', `${base}^{commit}`], { cwd })
        git(['cat-file', '-e', `${head}^{commit}`], { cwd })
      } catch {
        unavailable = 'comparison base or pushed commit absent from the clone'
      }
      if (unavailable === null) {
        try {
          const out = git(['diff', '--name-only', '--no-renames', base, head], { cwd })
          changedPaths = out.split('\n').filter((line) => line !== '')
        } catch {
          unavailable = 'git diff failed'
        }
      }
    }
    // A value that is not a commit id is treated as unreadable and never echoed.
    return decide({
      environment,
      base: COMMIT_ID.test(base) ? base : '',
      head: COMMIT_ID.test(head) ? head : '',
      changedPaths,
      unavailable,
    })
  } catch (error) {
    return { exit: 1, line: `build: rule failed (${error?.name ?? 'error'})` }
  }
}

function main() {
  let result
  try {
    result = run(process.env)
  } catch {
    result = { exit: 1, line: 'build: rule failed' }
  }
  console.log(result.line)
  process.exitCode = result.exit
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main()
  } catch {
    process.exitCode = 1
  }
}
