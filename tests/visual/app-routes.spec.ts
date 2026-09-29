// T108: every other file in this directory screenshots packages/design-system's Storybook build —
// a story renders one component in isolation, imported straight from packages/design-system/src,
// which is exactly where Tailwind's automatic source detection happened to work (T107's fix).
// Nothing in that suite ever loads what apps/web actually builds, so T107's regression — every
// screen shipping as unstyled markup because apps/web's own source root was never declared to
// Tailwind — left all 66 Storybook baselines green while the deployed site was broken.
//
// This file serves the production build of apps/web itself (`apps/web/dist`, the same artefact
// `.github/workflows/pr.yml`'s `web` job builds for `scripts/checks/built-css.mjs`) from a static
// file server with an SPA fallback, stubs `/api/*` with Playwright's own route interception rather
// than running `apps/api` (constitution III: no network call outside `packages/providers`), and
// screenshots every route this application declares (`apps/web/src/routes/`, `index.tsx` excepted
// — it only ever redirects, so it never paints a landmark of its own to check).
//
// T553 (FR-022, SC-003): the check that matters in this file is not the screenshot at all — it is
// `expectExactlyOneMain` below. Counting `<main>` elements is cheap and machine-independent, which
// is exactly why this defect (a route nesting two landmarks, or a shell rendering none) survived
// 279 baselines on every authenticated route: nobody was counting, and a screenshot diff a person
// skims does not notice a landmark that duplicated without moving a pixel. Every route is captured
// in both themes too (`ds-theme-override`, seeded before navigation the way `ThemeProvider.tsx`
// reads it, and now asserted after navigation by `assertThemeApplied` — PR #102 review finding),
// because production-readiness item 13 ("every route in both themes") is otherwise a sentence with
// no harness behind it.
//
// PR #102 review finding M2: the fixture `/api/*` stubs and the route list used to be this file's
// own copy, duplicated (and drifting in lockstep with nothing) against `./fixtures/app-routes-
// harness.ts`'s identical `ROUTE_SCENARIOS`, itself walked by the four keyboard/focus-visibility/
// touch-footprint/reduced-motion sub-suites. Both now read the one list; `./fixtures/app-routes-
// harness.test.ts` is what keeps that list itself honest against `apps/web/src/routeTree.gen.ts`.
// This file keeps its own server bootstrap (`hasBuild`/`distDir`/the spawned `http-server`) and its
// own `expectExactlyOneMain`/`FULL_PAGE` — neither is duplicated fixture data, and the four
// sub-suites already have their own equivalent through `createAppServerHarness`.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import {
  assertThemeApplied,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way, not
// `import.meta.url`.
const rootDir = path.resolve(__dirname, '..', '..')
const distDir = path.join(rootDir, 'apps', 'web', 'dist')
const hasBuild = existsSync(path.join(distDir, 'index.html'))

// Distinct from Storybook's port (playwright.config.ts's `VISUAL_STORYBOOK_PORT`, default 6006)
// and from Vite's own preview default (4173), so a developer's stray `vite preview` never gets
// mistaken for this suite's server.
const port = process.env.VISUAL_APP_PORT ?? '4174'
const baseUrl = `http://127.0.0.1:${port}`

// A full-page screenshot of a built route carries far more anti-aliased text than an isolated
// component story — the whole sign-in screen or dashboard, plus the footer — so its cross-machine
// anti-aliasing drift is correspondingly larger: a baseline generated on one Linux renders ~2% of
// pixels different against another (GitHub's `ubuntu-latest` vs the Playwright container measured
// here), which clears playwright.config.ts's 0.01 default that the small component stories stay
// under. 0.05 absorbs that machine noise while staying an order of magnitude below the regression
// this suite exists to catch — T107's every-screen-unstyled defect changed essentially every
// pixel, not two in a hundred. Keeping the ratio here rather than in the config leaves the
// component floor tight and lets these baselines regenerate on any dev machine, the same way the
// design-system ones already do.
const FULL_PAGE = { fullPage: true, maxDiffPixelRatio: 0.05 } as const

let server: ChildProcess | undefined

async function isReachable(): Promise<boolean> {
  try {
    const response = await fetch(baseUrl)
    return response.ok
  } catch {
    return false
  }
}

async function waitUntilReachable(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await isReachable()) return
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`the built application's server never answered at ${baseUrl}`)
}

// FR-022/SC-003: the substance of T553. `getByRole('main')` reaches every `<main>` regardless of
// nesting depth — exactly the shape the pre-retrofit defect took (structural-tier.md §5's "ten
// deep in total") — so this fails loudly on zero (the shell rendered nothing) or two-or-more (a
// route still assembling its own landmark alongside `Page`'s), and the message names which route
// failed rather than leaving a bare "expected 1, received 2".
async function expectExactlyOneMain(page: Page, routeLabel: string): Promise<void> {
  await expect(
    page.getByRole('main'),
    `${routeLabel} must render exactly one main landmark`,
  ).toHaveCount(1)
}

function scenarioNamed(label: string) {
  const scenario = ROUTE_SCENARIOS.find((candidate) => candidate.label === label)
  if (!scenario) {
    throw new Error(
      `no ROUTE_SCENARIOS entry named '${label}' — has it been renamed or removed in ` +
        'tests/visual/fixtures/app-routes-harness.ts?',
    )
  }
  return scenario
}

const signInScenario = scenarioNamed('/sign-in')
const dashboardScenario = scenarioNamed('/dashboard')

// Every other route file under `apps/web/src/routes/` (`index.tsx` and the two above excepted —
// `index.tsx` only ever redirects, and `/sign-in`/`/dashboard` are already exercised, in both
// themes, by the four tests below through that same redirect). Each entry's stub comes from
// `ROUTE_SCENARIOS`; this file only adds the screenshot base name its own baselines are keyed on.
const SCREENSHOT_BASE_BY_LABEL: Readonly<Record<string, { screenshotBase: string }>> = {
  '/search': { screenshotBase: 'app-signed-in-search' },
  '/favourites': { screenshotBase: 'app-signed-in-favourites' },
  '/matches': { screenshotBase: 'app-signed-in-matches' },
  '/matches/$gameId': { screenshotBase: 'app-signed-in-match-detail' },
  '/players/$profileId': { screenshotBase: 'app-signed-in-player-profile' },
  '/players/$profileId/matches': { screenshotBase: 'app-signed-in-player-matches' },
  '/privacy': { screenshotBase: 'app-signed-in-privacy' },
  '/privacy-notice': { screenshotBase: 'app-signed-out-privacy-notice' },
  '/object': { screenshotBase: 'app-signed-out-object' },
}

const routeCases = ROUTE_SCENARIOS.filter(
  (scenario) => scenario.label !== '/sign-in' && scenario.label !== '/dashboard',
).map((scenario) => {
  const screenshotBase = SCREENSHOT_BASE_BY_LABEL[scenario.label]?.screenshotBase
  if (!screenshotBase) {
    throw new Error(
      `ROUTE_SCENARIOS has an entry ('${scenario.label}') with no screenshot base name in ` +
        'tests/visual/app-routes.spec.ts — add one to SCREENSHOT_BASE_BY_LABEL.',
    )
  }
  return { ...scenario, screenshotBase }
})

test.describe('the built application, served and stubbed', () => {
  // Serial rather than `fullyParallel`'s default (playwright.config.ts): every test below shares
  // one static server, started once in `beforeAll` and torn down in `afterAll` — full parallelism
  // would risk two workers racing to bind the same port.
  test.describe.configure({ mode: 'serial' })

  // Mirrors `scripts/visual/run.mjs`'s own "nothing to test yet" short-circuit for a missing
  // Storybook build: a skip here is not the T015a/T038b/T108 failure shape it looks like, because
  // `.github/workflows/pr.yml`'s `visual` job always runs `pnpm --filter web build` immediately
  // before this file — the skip only ever fires for a developer running this file in isolation
  // without having built first, the same case `run.mjs` prints a message for and exits 0 on.
  //
  // PR #102 review finding (low): that reasoning only holds in CI. A bare `test.skip` reports this
  // whole suite as passed either way, so a CI misconfiguration that skips the build step (or moves
  // this suite ahead of it) would pass silently instead of failing loudly — exactly the false
  // negative `expectExactlyOneMain`'s own docstring above warns a screenshot diff cannot catch on
  // its own. `process.env.CI` (set by every GitHub Actions runner) is what tells the two cases
  // apart; only a developer running this file locally without having built first gets the skip.
  if (!hasBuild && process.env.CI) {
    test('apps/web/dist must be built before this suite runs in CI', () => {
      throw new Error(
        'apps/web/dist has not been built. `.github/workflows/pr.yml` always runs ' +
          '`pnpm --filter web build` before this suite — a missing build here means that step ' +
          'failed or was skipped, not that this suite has nothing to test.',
      )
    })
  } else {
    test.skip(
      () => !hasBuild,
      'apps/web/dist has not been built — run `pnpm --filter web build` first.',
    )

    test.beforeAll(async () => {
      if (await isReachable()) {
        // Another worker already bound this port (or a developer has their own server running on
        // it) — reuse it rather than fail on `--strictPort`, the same idea Playwright's own
        // `webServer.reuseExistingServer` expresses for the Storybook server this config already
        // starts.
        return
      }
      // `-P <self>?` is `http-server`'s SPA fallback (a root devDependency already — the same tool
      // playwright.config.ts uses to serve Storybook): any request that does not resolve to a file
      // under apps/web/dist is proxied back to this server's own root, which serves `index.html`.
      // Verified against a real build: `/dashboard` and `/sign-in` both answer 200 with the shell,
      // matching what Vercel's own catch-all rewrite (T109, vercel.json) does in production, while
      // a built asset under `/assets/` still answers straight from disk rather than being
      // swallowed by it.
      server = spawn(
        'pnpm',
        ['exec', 'http-server', distDir, '--port', port, '-P', `${baseUrl}?`, '--silent'],
        { cwd: rootDir, stdio: 'ignore' },
      )
      await waitUntilReachable(20_000)
    })

    test.afterAll(() => {
      // A no-op when this worker found the port already reachable above and never spawned
      // anything.
      server?.kill()
    })

    test('a signed-out visitor lands on the sign-in screen (light)', async ({ page }) => {
      await seedThemeOverride(page, 'light')
      await signInScenario.stub(page)

      // `__root.tsx`'s `beforeLoad` resolves the session through `GET /api/me` before anything
      // paints; `routes/index.tsx`'s own `beforeLoad` then redirects an unauthenticated visitor to
      // `/sign-in` — the root itself never renders, so this is the same landing an ordinary
      // signed-out visit produces.
      await page.goto(`${baseUrl}${signInScenario.path}`)
      await page.waitForURL('**/sign-in')
      await assertThemeApplied(page, 'light')
      await expect(page.getByRole('button', { name: 'Continue with Steam' })).toBeVisible()
      await expectExactlyOneMain(page, '/sign-in')

      await waitForFontsReady(page)
      await expect(page).toHaveScreenshot('app-signed-out-sign-in.png', FULL_PAGE)
    })

    test('a signed-out visitor lands on the sign-in screen (dark)', async ({ page }) => {
      await seedThemeOverride(page, 'dark')
      await signInScenario.stub(page)

      await page.goto(`${baseUrl}${signInScenario.path}`)
      await page.waitForURL('**/sign-in')
      await assertThemeApplied(page, 'dark')
      await expect(page.getByRole('button', { name: 'Continue with Steam' })).toBeVisible()
      await expectExactlyOneMain(page, '/sign-in')

      await waitForFontsReady(page)
      await expect(page).toHaveScreenshot('app-signed-out-sign-in-dark.png', FULL_PAGE)
    })

    test('a signed-in visitor lands on the dashboard (light)', async ({ page }) => {
      await seedThemeOverride(page, 'light')
      await dashboardScenario.stub(page)

      await page.goto(`${baseUrl}${dashboardScenario.path}`)
      await page.waitForURL('**/dashboard')
      await assertThemeApplied(page, 'light')
      await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
      await expect(page.getByText('VisualSuitePlayer')).toBeVisible()
      await expectExactlyOneMain(page, '/dashboard')

      await waitForFontsReady(page)
      await expect(page).toHaveScreenshot('app-signed-in-dashboard.png', FULL_PAGE)
    })

    test('a signed-in visitor lands on the dashboard (dark)', async ({ page }) => {
      await seedThemeOverride(page, 'dark')
      await dashboardScenario.stub(page)

      await page.goto(`${baseUrl}${dashboardScenario.path}`)
      await page.waitForURL('**/dashboard')
      await assertThemeApplied(page, 'dark')
      await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
      await expect(page.getByText('VisualSuitePlayer')).toBeVisible()
      await expectExactlyOneMain(page, '/dashboard')

      await waitForFontsReady(page)
      await expect(page).toHaveScreenshot('app-signed-in-dashboard-dark.png', FULL_PAGE)
    })

    for (const routeCase of routeCases) {
      for (const theme of ['light', 'dark'] as const) {
        test(`${routeCase.label} renders exactly one main landmark (${theme})`, async ({
          page,
        }) => {
          await seedThemeOverride(page, theme)
          await routeCase.stub(page)

          await page.goto(`${baseUrl}${routeCase.path}`)
          await assertThemeApplied(page, theme)
          await expectExactlyOneMain(page, routeCase.label)

          await waitForFontsReady(page)
          const screenshotName =
            theme === 'light'
              ? `${routeCase.screenshotBase}.png`
              : `${routeCase.screenshotBase}-dark.png`
          await expect(page).toHaveScreenshot(screenshotName, FULL_PAGE)
        })
      }
    }
  }
})
