// Visual regression config (T005). Targets Storybook stories built by
// `pnpm --filter design-system build-storybook` (packages/design-system/storybook-static),
// never a live dev server — constitution VII wants a stable, reproducible artefact under test.
//
// This file intentionally knows nothing about *which* stories run: `scripts/visual/run.mjs` picks
// that (all of them, or only the ones a diff touched) before ever invoking Playwright, so that the
// case of "no stories exist yet" and the case of "no story changed" both short-circuit before this
// config's webServer would need to start. See that script for the diff-scoping logic.
import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

// Playwright loads this file as CommonJS unless the nearest package.json sets
// `"type": "module"`, so `__dirname` (not `import.meta.url`) is what stays valid either way.
const rootDir = __dirname
const storybookStaticDir = path.join(rootDir, 'packages/design-system/storybook-static')
const screenshotsDir = path.join(rootDir, 'packages/design-system/__screenshots__')
const storybookPort = process.env.VISUAL_STORYBOOK_PORT ?? '6006'

// T673: true only for the dedicated determinism run (`RUN_DETERMINISM=1`, set only by
// `.github/workflows/nightly.yml`'s `visual-full` job) — read once here, not per-project, because
// it gates three things together: which one project is registered (below), where that project's
// own screenshots land (`determinismSnapshotDir`, `determinismProject.snapshotPathTemplate`), and
// whether a *missing* snapshot writes-and-passes rather than writes-and-fails (`updateSnapshots`,
// see its own comment below). `test-results/` is gitignored and the default when
// `VISUAL_DETERMINISM_DIR` is unset, so a determinism run never needs a pre-existing baseline —
// `story-determinism.mjs`'s own default pass directories (`test-results/determinism/pass-0`,
// `pass-1`) are this path's own children, kept in sync by construction rather than restated.
const determinismMode = process.env.RUN_DETERMINISM === '1'
const determinismSnapshotDir = path.resolve(
  rootDir,
  process.env.VISUAL_DETERMINISM_DIR ?? 'test-results/determinism',
)

export default defineConfig({
  testDir: './tests/visual',
  snapshotPathTemplate: `${screenshotsDir}/{arg}{ext}`,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // T510: raised from 2 to 4 once the matrix (T504) put every affected story through six capture
  // units instead of one — GitHub's standard `ubuntu-latest` runner has 4 vCPUs, so this matches
  // the box rather than overcommitting it. Throughput only; the comparison itself (`expect` above)
  // and the settle logic in `tests/visual/stories.spec.ts` are unchanged.
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${storybookPort}`,
    trace: 'retain-on-failure',
  },
  expect: {
    // Fonts and anti-aliasing differ marginally between machines; this keeps baselines stable
    // without hiding a real regression.
    toHaveScreenshot: { maxDiffPixelRatio: 0.01 },
  },
  // T673: whenever `determinismMode` is true, every capture in `tests/visual/stories.spec.ts`'s
  // `determinism`-mode branch is, by construction, being written for the first time (a fresh
  // `test-results/determinism` directory, one subdirectory per `repeatEachIndex`) — so this is
  // never a real regression comparison. `updateSnapshots` is a config-*level* setting only (there
  // is no per-project override in the installed `playwright@1.62.1` — confirmed by reading
  // `TestProject` in `node_modules/playwright/types/test.d.ts`, which carries no such field, and
  // by tracing `SnapshotHelper.updateSnapshots` in `node_modules/playwright/lib/matchers/
  // expect.js` back to `testInfo.config.updateSnapshots`, the whole run's `FullConfig`), which is
  // exactly why `determinismMode` also decides which *project* is registered below: the two
  // settings only ever travel together, so `updateSnapshots: 'all'` can never apply to a
  // `chromium` run that asserts against a real, checked-in baseline.
  //
  // Verified empirically against this installed version, not assumed: the *default* mode,
  // `'missing'` (left in place whenever `determinismMode` is false, by omitting the key entirely
  // — the normal baseline path is unchanged), does write a missing snapshot but still fails the
  // test (`SnapshotHelper.handleMissing`'s `softError`, promoted to a real failure by
  // `workerProcessEntry.js`'s `_failWithError` even though the matcher itself returns
  // `pass: true`). `'all'` writes the same file with no `softError`, so the test passes — the
  // "write and pass" mode this harness needs.
  ...(determinismMode ? { updateSnapshots: 'all' as const } : {}),
  webServer: {
    // Serves the static Storybook build produced by the `build-storybook` step. Never a dev
    // server: a dev server rebuilds and hot-reloads, which is exactly the nondeterminism visual
    // regression exists to catch elsewhere.
    command: `pnpm exec http-server "${storybookStaticDir}" --port ${storybookPort} --silent`,
    url: `http://127.0.0.1:${storybookPort}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  // T673: the determinism harness re-renders `tests/visual/stories.spec.ts` itself — never a
  // second copy of its settle/force-state/clip logic — twice, and `scripts/checks/
  // story-determinism.mjs` compares the two renders directly. `repeatEach: 2` on a `determinism`
  // project targeting that same spec file is what produces the second render, in the same
  // `playwright test` invocation, without a second spec file or a second config file; the spec
  // itself switches only the *name* it passes to `toHaveScreenshot` under `determinismMode` (see
  // that file's own comment at the switch) — every branch still calls the same matcher, with the
  // same defaults and the same stability loop, so both passes go through the exact render path
  // the baseline suite captures, never a narrower copy of it. This project's own
  // `snapshotPathTemplate` resolves that name into `determinismSnapshotDir` rather than the global
  // `screenshotsDir` above, so nothing this project captures can land under
  // `packages/design-system/__screenshots__`.
  //
  // The whole `projects` array swaps to this one project, replacing `chromium` rather than adding
  // to it, only when `RUN_DETERMINISM=1` — `testMatch` alone cannot make this opt-in, because a
  // project with no `--project` filter on the *invocation* still runs by default on every plain
  // `playwright test` call, and both would otherwise run together. Both `scripts/visual/run.mjs`
  // (`pnpm test:visual` / `--changed`, used by every pull request) and `pr.yml`'s direct
  // `tests/visual/app-routes.spec.ts` call are exactly that shape — neither ever passes
  // `--project`, so an always-registered `determinism` project would silently double every
  // story's capture cost on every pull request, the one thing this task's own sizing forbids
  // (`.github/workflows/nightly.yml`'s `visual-full` job is the only caller that sets this var,
  // paired with `VISUAL_DETERMINISM_DIR`).
  projects: determinismMode
    ? [
        {
          name: 'determinism',
          testMatch: /stories\.spec\.ts$/,
          use: { ...devices['Desktop Chrome'] },
          repeatEach: 2,
          snapshotPathTemplate: `${determinismSnapshotDir}/{arg}{ext}`,
        },
      ]
    : [
        {
          name: 'chromium',
          use: { ...devices['Desktop Chrome'] },
        },
      ],
})
