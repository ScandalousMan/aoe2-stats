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
  webServer: {
    // Serves the static Storybook build produced by the `build-storybook` step. Never a dev
    // server: a dev server rebuilds and hot-reloads, which is exactly the nondeterminism visual
    // regression exists to catch elsewhere.
    command: `pnpm exec http-server "${storybookStaticDir}" --port ${storybookPort} --silent`,
    url: `http://127.0.0.1:${storybookPort}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
