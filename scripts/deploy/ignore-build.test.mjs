// T810: the build-skip rule's test (FR-009, SC-003). Four groups:
//   1. recorded history: real `main` ranges, changed paths embedded as literals (no git history
//      needed in CI, whose checkout is shallow);
//   2. throwaway repositories, for what history cannot show;
//   3. verdict integrity (FR-008, amended): verdicts, not disjointness, because the lists overlap;
//   4. glob shapes.
//
// The rename and baseline-only cases below are CONSTRUCTED, not recorded (research R4):
// `main`'s history holds no cross-root rename and no commit that touches only visual baselines,
// so FR-009's "real commit ranges" is met for those two shapes by a synthetic range.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import { chmodSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { delimiter, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  ALWAYS_DEPLOY,
  GIT_TIMEOUT_MS,
  decide,
  globToRegExp,
  run,
  runGit,
} from './ignore-build.mjs'

const RULE = join(dirname(fileURLToPath(import.meta.url)), 'ignore-build.mjs')
const SHA_A = 'a'.repeat(40)
const SHA_B = 'b'.repeat(40)

// --- 1. Recorded history ---------------------------------------------------------------------
// Captured once with `git diff --name-only --no-renames <base> <head>` on `main`.

const RECORDED = [
  {
    name: 'docs-only commit',
    base: '17293807686ad478383373279a0108f02c579897',
    head: '4513ac6c4365280323f65c709e2b4549ff9d78c3',
    expected: 'skip',
    why: 'prose only',
    paths: [
      'specs/006-replay-analysis-foundations/quickstart.md',
      'specs/006-replay-analysis-foundations/tasks.md',
    ],
  },
  {
    name: 'tasks-only commit',
    base: '514aec69d48bbd097011e80facebae8d20f1ba34',
    head: '326bd1306aaf2ed3cc8b12d30cf05b273431b85e',
    expected: 'skip',
    why: 'spec-kit artifact only',
    paths: ['specs/006-replay-analysis-foundations/tasks.md'],
  },
  {
    name: 'tests-and-specs commit',
    base: '27e2a806cc7eb717acc8ef6d1d8ffba80f8c600e',
    head: '0497064505fb5fb357cca6e358de9dffc6d0ccba',
    expected: 'skip',
    why: 'tests and specs only',
    paths: [
      'packages/design-system/specs/README.md',
      'specs/005-design-system-foundations/quickstart.md',
      'specs/005-design-system-foundations/tasks.md',
      'tests/visual/fixtures/keyboard-walk.test.ts',
      'tests/visual/fixtures/keyboard-walk.ts',
      'tests/visual/fixtures/suite-scenarios.test.ts',
      'tests/visual/fixtures/suite-scenarios.ts',
      'tests/visual/fixtures/tooltip-open.test.ts',
      'tests/visual/fixtures/tooltip-open.ts',
      'tests/visual/route-keyboard.spec.ts',
      'tests/visual/route-reduced-motion.spec.ts',
    ],
  },
  {
    name: 'token-test commit',
    base: '708273a3ebdc6341e4851e19aadd813ce6a70dff',
    head: 'e394735ffeae5583ccc833b3c291fad708a08212',
    expected: 'skip',
    why: 'a token test only',
    paths: [
      'packages/design-system/specs/color-tokens.md',
      'packages/design-system/tokens/color-tokens-citations.test.mjs',
      'specs/005-design-system-foundations/tasks.md',
    ],
  },
  {
    name: 'uv.lock commit',
    base: 'e6357158497393163154564fd45df02aba5df9b6',
    head: '4d99e5a080594e7a6317d8187d5d61692f7baba1',
    expected: 'build',
    why: 'the lock decides what the bundle installs',
    paths: [
      '.claude/skills/replay-parsing/SKILL.md',
      'apps/analyzer/src/aoe2stats_analyzer/run.py',
      'apps/analyzer/tests/test_engine_panic.py',
      'docs/adr/0001-replay-parser.md',
      'docs/privacy/processing-register.md',
      'docs/risks.md',
      'packages/replay-engine/pyproject.toml',
      'packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py',
      'packages/replay-engine/src/aoe2stats_replay_engine/canonical.py',
      'packages/replay-engine/tests/test_aoe2rec.py',
      'packages/replay-engine/tests/test_build_185872.py',
      'packages/replay-engine/tests/test_canonical.py',
      'packages/replay-engine/tests/test_canonical_collapse.py',
      'scripts/checks/parser_canary.py',
      'specs/006-replay-analysis-foundations/tasks.md',
      'tests/fixtures/replays/AgeIIDE_Replay_500546441.timeline.json',
      'tests/fixtures/replays/AgeIIDE_Replay_511523321.canonical.json',
      'tests/fixtures/replays/AgeIIDE_Replay_511523321.zip',
      'tests/fixtures/replays/README.md',
      'tests/test_reference_recordings.py',
      'uv.lock',
    ],
  },
  {
    name: 'migration commit',
    base: '0c11583667a13420a9c63b08f83f2f2da6904a17',
    head: '754f022ae6777728a35dcecb766574371b10b22e',
    expected: 'build',
    why: 'a migration ships',
    paths: [
      '.env.example',
      'apps/analyzer/src/aoe2stats_analyzer/admission.py',
      'apps/analyzer/tests/test_admission.py',
      'apps/api/src/aoe2stats_api/ingest_stages.py',
      'apps/api/src/aoe2stats_api/routers/profiles.py',
      'apps/api/src/aoe2stats_api/routers/replays.py',
      'apps/api/src/aoe2stats_api/settings.py',
      'apps/api/tests/conftest.py',
      'apps/api/tests/test_ingest_stages.py',
      'apps/api/tests/test_replay_status.py',
      'apps/api/tests/test_settings.py',
      'apps/ingester/src/aoe2stats_ingester/capture.py',
      'apps/ingester/src/aoe2stats_ingester/run.py',
      'apps/ingester/tests/test_capture_run_id.py',
      'apps/ingester/tests/test_claim_requires_active_link.py',
      'apps/ingester/tests/test_deadline_alert.py',
      'apps/ingester/tests/test_deadline_order.py',
      'apps/ingester/tests/test_failure_classification.py',
      'apps/ingester/tests/test_idempotency.py',
      'apps/ingester/tests/test_interruption.py',
      'apps/ingester/tests/test_quarantine.py',
      'apps/ingester/tests/test_revalidate_quarantined.py',
      'apps/ingester/tests/test_withdraw_refused_near_deadline.py',
      'infra/migrations/versions/19b5ac9aa12c_replay_capture_status_withdrawn.py',
      'packages/storage/src/aoe2stats_storage/models.py',
      'packages/storage/src/aoe2stats_storage/repositories/matches.py',
      'packages/storage/src/aoe2stats_storage/revision.py',
      'packages/storage/tests/repositories/test_matches.py',
      'packages/storage/tests/test_migration_analysis_knowledge_gaps.py',
      'packages/storage/tests/test_migration_capture_status_withdrawn.py',
      'packages/storage/tests/test_models.py',
      'scripts/checks/capture_audit.py',
      'scripts/checks/tests/test_capture_audit.py',
      'scripts/ops/revalidate_quarantined.py',
      'specs/006-replay-analysis-foundations/tasks.md',
      'tests/links.py',
    ],
  },
  {
    name: 'root package.json and pnpm-lock.yaml commit',
    base: 'a4d13ba550b2ceeefdda159d75341b56440433ea',
    head: 'b2899e2d4e61c0e36dc2fb435d138fc9eabd0b19',
    expected: 'build',
    why: 'dependency manifests',
    paths: [
      '.github/workflows/pr.yml',
      'package.json',
      'packages/design-system/specs/README.md',
      'pnpm-lock.yaml',
      'scripts/checks/state-coverage.mjs',
      'scripts/checks/state-coverage.test.mjs',
      'scripts/visual/a11y-scan.d.cts',
      'scripts/visual/instance-identity.d.mts',
      'scripts/visual/instance-identity.mjs',
      'scripts/visual/module-specifiers.mjs',
      'scripts/visual/run.mjs',
      'scripts/visual/state-coverage-runtime-model.mjs',
      'scripts/visual/state-coverage-runtime-model.test.mjs',
      'scripts/visual/state-signal-model.mjs',
      'scripts/visual/story-index.mjs',
      'scripts/visual/story-index.test.mjs',
      'scripts/visual/story-selection.mjs',
      'scripts/visual/story-selection.test.mjs',
      'specs/005-design-system-foundations/tasks.md',
      'tests/visual/fixtures/story-page-stub.ts',
      'tests/visual/pngjs.d.ts',
      'tests/visual/state-coverage-runtime-probe.spec.ts',
      'tests/visual/state-coverage-runtime.spec.ts',
      'tests/visual/state-coverage-runtime.ts',
      'tests/visual/state-signal-sweep.spec.ts',
      'tests/visual/stories.spec.ts',
      'tests/visual/story-render.ts',
      'tests/visual/tsconfig.check.json',
    ],
  },
  {
    name: 'vercel.json and .vercelignore commit',
    base: '4805469ecf7742c305aa1b51cfc784b99e7063ba',
    head: '67ecc12b6d17c08bb7eb3ba5bb64a6980f04242a',
    expected: 'build',
    why: 'host configuration',
    paths: ['.vercelignore', 'docs/adr/0002-hosting.md', 'docs/risks.md', 'vercel.json'],
  },
  {
    name: 'api/ together with docs (mixed) commit',
    base: '4a599f413eb1dbc0969f419cb084632f1e3eba7e',
    head: '40072fa770389125238289736ad9df82b6cb22c7',
    expected: 'build',
    why: 'a shipped path beside prose',
    paths: [
      '.env.example',
      'api/analyze.py',
      'apps/analyzer/src/aoe2stats_analyzer/claim.py',
      'apps/analyzer/src/aoe2stats_analyzer/run.py',
      'apps/analyzer/tests/test_claim.py',
      'apps/analyzer/tests/test_engine_panic.py',
      'apps/analyzer/tests/test_gap_rows.py',
      'apps/analyzer/tests/test_reproducibility.py',
      'apps/analyzer/tests/test_run_once.py',
      'apps/api/src/aoe2stats_api/routers/matches.py',
      'apps/api/src/aoe2stats_api/settings.py',
      'apps/api/tests/conftest.py',
      'apps/api/tests/test_analysis_routes.py',
      'apps/api/tests/test_analyze_entrypoint.py',
      'apps/api/tests/test_settings.py',
      'apps/web/src/features/analysis/AnalysisContainer.test.tsx',
      'apps/web/src/features/analysis/AnalysisContainer.tsx',
      'apps/web/src/features/analysis/api.test.ts',
      'apps/web/src/features/analysis/api.ts',
      'packages/design-system/specs/analysis-timeline.md',
      'packages/design-system/src/composites/AnalysisTimeline/AnalysisTimeline.test.tsx',
      'packages/design-system/src/composites/AnalysisTimeline/index.tsx',
      'packages/storage/src/aoe2stats_storage/models.py',
      'scripts/checks/config-preflight.mjs',
      'specs/006-replay-analysis-foundations/tasks.md',
      'tests/visual/fixtures/suite-scenarios.ts',
    ],
  },
  {
    name: 'docs-only head over an undeployed code commit',
    base: '4513ac6c4365280323f65c709e2b4549ff9d78c3',
    head: '0497064505fb5fb357cca6e358de9dffc6d0ccba',
    expected: 'build',
    why: 'the base is the last deployed commit, so the earlier code commit is in the range',
    paths: [
      'apps/analyzer/src/aoe2stats_analyzer/methods.py',
      'apps/analyzer/src/aoe2stats_analyzer/names.py',
      'apps/analyzer/tests/test_names.py',
      'apps/web/src/features/analysis/api.test.ts',
      'packages/core/src/aoe2stats_core/truth/REGISTER.md',
      'packages/core/src/aoe2stats_core/truth/register.toml',
      'packages/design-system/specs/README.md',
      'specs/005-design-system-foundations/quickstart.md',
      'specs/005-design-system-foundations/tasks.md',
      'specs/006-replay-analysis-foundations/contracts/analysis-document.md',
      'specs/006-replay-analysis-foundations/tasks.md',
      'tests/visual/fixtures/keyboard-walk.test.ts',
      'tests/visual/fixtures/keyboard-walk.ts',
      'tests/visual/fixtures/suite-scenarios.test.ts',
      'tests/visual/fixtures/suite-scenarios.ts',
      'tests/visual/fixtures/tooltip-open.test.ts',
      'tests/visual/fixtures/tooltip-open.ts',
      'tests/visual/route-keyboard.spec.ts',
      'tests/visual/route-reduced-motion.spec.ts',
    ],
  },
]

for (const fixture of RECORDED) {
  test(`recorded history: ${fixture.name} -> ${fixture.expected} (${fixture.why})`, () => {
    const result = decide({
      environment: 'production',
      base: fixture.base,
      head: fixture.head,
      changedPaths: fixture.paths,
    })
    assert.equal(result.exit, fixture.expected === 'skip' ? 0 : 1, result.line)
    assert.match(result.line, new RegExp(`^${fixture.expected}: `))
  })
}

test('recorded history: a non-production build of a commit that would deploy skips', () => {
  const deploys = RECORDED.find((f) => f.name === 'uv.lock commit')
  const result = decide({
    environment: 'preview',
    base: deploys.base,
    head: deploys.head,
    changedPaths: deploys.paths,
  })
  assert.deepEqual(result, { exit: 0, line: 'skip: non-production (preview)' })
})

// --- 2. Throwaway repositories ---------------------------------------------------------------

const IDENTITY = ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid']

function git(cwd, ...args) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
}

function commitFiles(cwd, files, message) {
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(dirname(join(cwd, path)), { recursive: true })
    writeFileSync(join(cwd, path), content)
  }
  git(cwd, 'add', '-A')
  git(cwd, ...IDENTITY, 'commit', '-q', '-m', message)
  return git(cwd, 'rev-parse', 'HEAD').trim()
}

function makeRepo() {
  const dir = mkdtempSync(join(tmpdir(), 'ignore-build-'))
  git(dir, 'init', '-q')
  return dir
}

/** Run the real entry as a child process the way the host does. */
function entry(cwd, vars) {
  const env = { PATH: process.env.PATH, ...vars }
  const result = spawnSync(process.execPath, [RULE], { cwd, env, encoding: 'utf8' })
  return { status: result.status, stdout: result.stdout.trim() }
}

function withRepo(fn) {
  const dir = makeRepo()
  try {
    fn(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

const prod = (base, head) => ({
  VERCEL_ENV: 'production',
  VERCEL_GIT_PREVIOUS_SHA: base,
  VERCEL_GIT_COMMIT_SHA: head,
})

test('throwaway: a docs-only range skips, and prints one contract line', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'api/index.py': 'x', 'docs/a.md': 'a' }, 'one')
    const head = commitFiles(dir, { 'docs/a.md': 'b', 'specs/x.md': 'c' }, 'two')
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 0)
    assert.equal(out.stdout, `skip: nothing shipped between ${base} and ${head} (2 paths)`)
  })
})

test('throwaway: every commit in the range counts, not only the last', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    commitFiles(dir, { 'api/index.py': 'x' }, 'code')
    const head = commitFiles(dir, { 'docs/a.md': 'b' }, 'docs')
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 1)
    assert.equal(out.stdout, `build: api/index.py (${base}..${head})`)
  })
})

test('throwaway: absent base variable builds', () => {
  withRepo((dir) => {
    const head = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const out = entry(dir, { VERCEL_ENV: 'production', VERCEL_GIT_COMMIT_SHA: head })
    assert.deepEqual(out, { status: 1, stdout: 'build: comparison base unreadable' })
  })
})

test('throwaway: empty base builds', () => {
  withRepo((dir) => {
    const head = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const out = entry(dir, prod('', head))
    assert.deepEqual(out, { status: 1, stdout: 'build: comparison base unreadable' })
  })
})

test('throwaway: a base that is not a commit id is never echoed and builds', () => {
  withRepo((dir) => {
    const head = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const out = entry(dir, prod('--output=/x; secret', head))
    assert.deepEqual(out, { status: 1, stdout: 'build: comparison base unreadable' })
  })
})

test('throwaway: a base absent from the repository builds', () => {
  withRepo((dir) => {
    const head = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const out = entry(dir, prod(SHA_A, head))
    assert.deepEqual(out, {
      status: 1,
      stdout: 'build: comparison base or pushed commit absent from the clone',
    })
  })
})

test('throwaway: a base missing from a shallow clone builds', () => {
  withRepo((source) => {
    const base = commitFiles(source, { 'docs/a.md': 'a' }, 'one')
    commitFiles(source, { 'docs/a.md': 'b' }, 'two')
    const head = commitFiles(source, { 'docs/a.md': 'c' }, 'three')
    const parent = mkdtempSync(join(tmpdir(), 'ignore-build-clone-'))
    try {
      const clone = join(parent, 'clone')
      // `file://` is required for --depth; this reads the local throwaway repository only.
      git(parent, 'clone', '-q', '--depth', '1', `file://${source}`, clone)
      const out = entry(clone, prod(base, head))
      assert.deepEqual(out, {
        status: 1,
        stdout: 'build: comparison base or pushed commit absent from the clone',
      })
    } finally {
      rmSync(parent, { recursive: true, force: true })
    }
  })
})

test('throwaway: base equal to head (a redeploy) builds', () => {
  withRepo((dir) => {
    const head = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const out = entry(dir, prod(head, head))
    assert.equal(out.status, 1)
    assert.equal(out.stdout, `build: no changed path (${head}..${head})`)
  })
})

test('throwaway: a non-production target skips whatever changed', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const head = commitFiles(dir, { 'uv.lock': 'x' }, 'lock')
    for (const environment of ['preview', 'development']) {
      const out = entry(dir, { ...prod(base, head), VERCEL_ENV: environment })
      assert.deepEqual(out, { status: 0, stdout: `skip: non-production (${environment})` })
    }
  })
})

test('throwaway: a non-production target skips even with no readable base', () => {
  const out = entry(tmpdir(), { VERCEL_ENV: 'preview' })
  assert.deepEqual(out, { status: 0, stdout: 'skip: non-production (preview)' })
})

test('throwaway: a target that cannot be read builds', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const head = commitFiles(dir, { 'docs/a.md': 'b' }, 'two')
    const { VERCEL_ENV: _omitted, ...rest } = prod(base, head)
    assert.deepEqual(entry(dir, rest), {
      status: 1,
      stdout: 'build: target environment unreadable',
    })
    assert.deepEqual(entry(dir, { ...rest, VERCEL_ENV: '' }), {
      status: 1,
      stdout: 'build: target environment unreadable',
    })
  })
})

test('throwaway: not a git repository builds (git diff fails)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ignore-build-nogit-'))
  try {
    const out = entry(dir, prod(SHA_A, SHA_B))
    assert.equal(out.status, 1)
    assert.match(out.stdout, /^build: /)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('throwaway (constructed, not recorded): a rename from a never-shipped path into a shipped one builds', () => {
  withRepo((dir) => {
    const body = 'identical content so git would pair this as a rename\n'.repeat(20)
    const base = commitFiles(dir, { 'docs/handler.py': body }, 'one')
    mkdirSync(join(dir, 'api'))
    git(dir, 'mv', 'docs/handler.py', 'api/handler.py')
    git(dir, ...IDENTITY, 'commit', '-q', '-m', 'rename')
    const head = git(dir, 'rev-parse', 'HEAD').trim()
    // The new name alone builds, so this passes with or without --no-renames; it shows only
    // that a rename into a shipped path builds. The opposite rename, below, proves both sides.
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 1)
    assert.equal(out.stdout, `build: api/handler.py (${base}..${head})`)
  })
})

test('throwaway (constructed, not recorded): a rename out of a shipped path builds', () => {
  withRepo((dir) => {
    // Rename detection on, whatever the machine's git configuration says, so the case means the
    // same everywhere: only --no-renames makes git list the old, shipped side.
    git(dir, 'config', 'diff.renames', 'true')
    const body = 'identical content so git would pair this as a rename\n'.repeat(20)
    const base = commitFiles(dir, { 'api/handler.py': body }, 'one')
    mkdirSync(join(dir, 'docs'))
    git(dir, 'mv', 'api/handler.py', 'docs/handler.py')
    git(dir, ...IDENTITY, 'commit', '-q', '-m', 'rename')
    const head = git(dir, 'rev-parse', 'HEAD').trim()
    // With renames on, `git diff --name-only` would list only docs/handler.py and skip. The rule
    // passes --no-renames so it lists both sides and finds the shipped one.
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 1)
    assert.equal(out.stdout, `build: api/handler.py (${base}..${head})`)
  })
})

test('throwaway (constructed, not recorded): a baseline-only commit skips', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'apps/web/src/main.tsx': 'x' }, 'one')
    const head = commitFiles(
      dir,
      { 'packages/design-system/__screenshots__/button/default.png': 'png' },
      'baselines',
    )
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 0)
    assert.equal(out.stdout, `skip: nothing shipped between ${base} and ${head} (1 paths)`)
  })
})

test('throwaway: a path that matched no list (a new top-level directory) builds', () => {
  withRepo((dir) => {
    const base = commitFiles(dir, { 'docs/a.md': 'a' }, 'one')
    const head = commitFiles(dir, { 'newdir/thing.txt': 'x', 'docs/a.md': 'b' }, 'two')
    const out = entry(dir, prod(base, head))
    assert.equal(out.status, 1)
    assert.equal(out.stdout, `build: newdir/thing.txt (${base}..${head})`)
  })
})

test('crash inside the rule exits 1, not 0', () => {
  // A getter that throws stands for any exception inside the rule's body.
  const env = {
    get VERCEL_ENV() {
      throw new TypeError('boom')
    },
  }
  const result = run(env)
  assert.equal(result.exit, 1)
  assert.match(result.line, /^build: /)
})

test('crash in every git call (commit check fails first) exits 1 with the absent-from-clone line', () => {
  const result = run(prod(SHA_A, SHA_B), {
    git: () => {
      throw new Error('git blew up')
    },
  })
  assert.deepEqual(result, {
    exit: 1,
    line: 'build: comparison base or pushed commit absent from the clone',
  })
})

test('crash in the diff itself (commit check succeeds) exits 1 with the git diff failed line', () => {
  const calls = []
  const result = run(prod(SHA_A, SHA_B), {
    git: (args) => {
      calls.push(args[0])
      if (args[0] === 'diff') throw new Error('git blew up')
      return ''
    },
  })
  assert.deepEqual(calls, ['cat-file', 'cat-file', 'diff'])
  assert.deepEqual(result, { exit: 1, line: 'build: git diff failed' })
})

test('a git timeout during the diff builds (FR-007)', () => {
  const result = run(prod(SHA_A, SHA_B), {
    git: (args) => {
      if (args[0] === 'diff') {
        throw Object.assign(new Error('spawnSync git ETIMEDOUT'), { code: 'ETIMEDOUT' })
      }
      return ''
    },
  })
  assert.deepEqual(result, { exit: 1, line: 'build: git diff failed' })
})

test('the default git runner times out on a hanging git instead of waiting for the host', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ignore-build-hang-'))
  const savedPath = process.env.PATH
  try {
    const fake = join(dir, 'git')
    writeFileSync(fake, '#!/bin/sh\nsleep 10\n')
    chmodSync(fake, 0o755)
    process.env.PATH = `${dir}${delimiter}${savedPath}`
    const started = Date.now()
    assert.throws(() => runGit(['diff'], { cwd: dir, timeoutMs: 200 }))
    assert.ok(Date.now() - started < 3000, 'the runner must give up within its timeout')
    // The same runner serves the cat-file calls, so they carry the timeout too.
    const startedCat = Date.now()
    assert.throws(() => runGit(['cat-file', '-e', 'x'], { cwd: dir, timeoutMs: 200 }))
    assert.ok(Date.now() - startedCat < 3000)
  } finally {
    process.env.PATH = savedPath
    rmSync(dir, { recursive: true, force: true })
  }
})

test('the default git timeout is 30 seconds', () => {
  assert.equal(GIT_TIMEOUT_MS, 30_000)
})

// --- 3. Verdict integrity (FR-008, amended) --------------------------------------------------

const verdict = (...paths) =>
  decide({ environment: 'production', base: SHA_A, head: SHA_B, changedPaths: paths }).exit

// One representative path per always-deploy entry.
const REPRESENTATIVE = {
  'infra/migrations/**': 'infra/migrations/versions/abc_add_table.py',
  '**/pyproject.toml': 'packages/storage/pyproject.toml',
  'uv.lock': 'uv.lock',
  '**/package.json': 'apps/web/package.json',
  'pnpm-lock.yaml': 'pnpm-lock.yaml',
  'vercel.json': 'vercel.json',
  '.vercelignore': '.vercelignore',
  '.env.example': '.env.example',
  'scripts/checks/config-preflight.mjs': 'scripts/checks/config-preflight.mjs',
  'api/**': 'api/cron/ingest.py',
  'scripts/deploy/**': 'scripts/deploy/ignore-build.mjs',
}

test('verdict integrity: every always-deploy entry has a representative', () => {
  assert.deepEqual(
    ALWAYS_DEPLOY.map(([pattern]) => pattern).sort(),
    Object.keys(REPRESENTATIVE).sort(),
  )
})

for (const [pattern, path] of Object.entries(REPRESENTATIVE)) {
  test(`verdict integrity: ${pattern} builds alone and beside docs/risks.md`, () => {
    assert.ok(globToRegExp(pattern).test(path), `${path} is not matched by ${pattern}`)
    assert.equal(verdict(path), 1)
    assert.equal(verdict('docs/risks.md', path), 1)
    assert.equal(verdict(path, 'docs/risks.md'), 1)
  })
}

test('verdict integrity: the root pyproject.toml builds too', () => {
  assert.equal(verdict('pyproject.toml'), 1)
  assert.equal(verdict('docs/risks.md', 'pyproject.toml'), 1)
})

for (const path of [
  'apps/api/src/aoe2stats_api/app.py',
  'apps/web/src/main.tsx',
  'packages/design-system/tokens/color.json',
  'packages/knowledge/src/aoe2stats_knowledge/snapshot.py',
]) {
  test(`verdict integrity: source path ${path} builds`, () => {
    assert.equal(verdict(path), 1)
    assert.equal(verdict('docs/risks.md', path), 1)
  })
}

test('verdict integrity: a web test and a design-system story skip', () => {
  assert.equal(verdict('apps/web/src/components/Thing.test.tsx'), 0)
  assert.equal(verdict('packages/design-system/src/Button.stories.tsx'), 0)
})

test('verdict integrity: scripts/** skips except the two carve-outs', () => {
  assert.equal(verdict('scripts/visual/run.mjs'), 0)
  assert.equal(verdict('scripts/checks/config-preflight.mjs'), 1)
  assert.equal(verdict('scripts/deploy/ignore-build.test.mjs'), 1)
})

test('verdict integrity: an empty change set never skips', () => {
  assert.equal(verdict(), 1)
})

// --- 4. Glob shapes --------------------------------------------------------------------------

test('glob: <dir>/** matches below the directory, not the directory name alone', () => {
  const re = globToRegExp('docs/**')
  assert.ok(re.test('docs/a.md') && re.test('docs/x/y.md'))
  assert.ok(!re.test('docsx/a.md') && !re.test('mydocs/a.md') && !re.test('docs'))
})

test('glob: a single-segment * does not cross a slash', () => {
  const re = globToRegExp('apps/*/tests/**')
  assert.ok(re.test('apps/api/tests/test_x.py'))
  assert.ok(!re.test('apps/api/src/tests/test_x.py') && !re.test('apps/tests/test_x.py'))
})

test('glob: a leading **/ matches at any depth including the root', () => {
  const re = globToRegExp('**/*.test.ts')
  assert.ok(re.test('a.test.ts') && re.test('apps/web/src/a.test.ts'))
  assert.ok(!re.test('apps/web/src/a.test.tsx') && !re.test('a.test.ts.bak'))
})

test('glob: regular expression metacharacters in a pattern are literal', () => {
  const re = globToRegExp('.claude/**')
  assert.ok(re.test('.claude/x') && !re.test('Xclaude/x'))
})

test('glob: an unsupported shape throws instead of matching wrongly', () => {
  assert.throws(() => globToRegExp('a/**/b'))
})
