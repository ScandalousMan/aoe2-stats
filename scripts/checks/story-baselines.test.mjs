// Regression tests for T503's mechanical check (story-baselines.mjs), and for the fix that
// widened its app-route exemption from two hardcoded names to the set derived from
// tests/visual/app-routes.spec.ts itself (see that file's header for why). Follows
// token-scale.test.mjs's own `node --test` conventions: real functions, no mocking,
// `node:assert/strict`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  loadAppRouteBaselineNames,
  findOrphanBaselines,
  findIncompleteStories,
  BASELINE_NAME_RE,
} from './story-baselines.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '..', '..')
const appRoutesSpecPath = path.join(rootDir, 'tests', 'visual', 'app-routes.spec.ts')

test('loadAppRouteBaselineNames derives the two literal captures plus every routeCases entry, doubled for the dark theme, from a small fixture', () => {
  const fixture = `
    await expect(page).toHaveScreenshot('app-signed-out-sign-in.png', FULL_PAGE)
    await expect(page).toHaveScreenshot('app-signed-out-sign-in-dark.png', FULL_PAGE)

    const routeCases: ReadonlyArray<{ screenshotBase: string }> = [
      { screenshotBase: 'app-signed-in-search' },
      { screenshotBase: 'app-signed-in-favourites' },
    ]
  `
  const names = loadAppRouteBaselineNames(fixture)
  assert.deepEqual(
    [...names].sort(),
    [
      'app-signed-in-favourites',
      'app-signed-in-favourites-dark',
      'app-signed-in-search',
      'app-signed-in-search-dark',
      'app-signed-out-sign-in',
      'app-signed-out-sign-in-dark',
    ].sort(),
  )
})

test('loadAppRouteBaselineNames does not match the routeCases type annotation itself (no literal follows the colon)', () => {
  const names = loadAppRouteBaselineNames('screenshotBase: string')
  assert.deepEqual([...names], [])
})

test('loadAppRouteBaselineNames against the real tests/visual/app-routes.spec.ts produces exactly the 22 names T553 introduced', () => {
  const source = readFileSync(appRoutesSpecPath, 'utf8')
  const names = loadAppRouteBaselineNames(source)

  const expected = [
    'app-signed-out-sign-in',
    'app-signed-out-sign-in-dark',
    'app-signed-in-dashboard',
    'app-signed-in-dashboard-dark',
    'app-signed-in-search',
    'app-signed-in-search-dark',
    'app-signed-in-favourites',
    'app-signed-in-favourites-dark',
    'app-signed-in-matches',
    'app-signed-in-matches-dark',
    'app-signed-in-match-detail',
    'app-signed-in-match-detail-dark',
    'app-signed-in-player-profile',
    'app-signed-in-player-profile-dark',
    'app-signed-in-player-matches',
    'app-signed-in-player-matches-dark',
    'app-signed-in-privacy',
    'app-signed-in-privacy-dark',
    'app-signed-out-privacy-notice',
    'app-signed-out-privacy-notice-dark',
    'app-signed-out-object',
    'app-signed-out-object-dark',
  ]

  assert.equal(names.size, 22)
  assert.deepEqual([...names].sort(), expected.sort())
})

test('findOrphanBaselines exempts every name loadAppRouteBaselineNames derives from the real spec file', () => {
  const exemptBaselines = loadAppRouteBaselineNames(readFileSync(appRoutesSpecPath, 'utf8'))
  const baselineFiles = [...exemptBaselines].map((name) => `${name}.png`)

  const orphans = findOrphanBaselines(baselineFiles, new Set(), exemptBaselines)
  assert.deepEqual(orphans, [])
})

test('findOrphanBaselines still reports a real orphan baseline that names no story', () => {
  const orphans = findOrphanBaselines(
    ['composite-button--primary-light-1280.png', 'composite-widget--ghost-light-1280.png'],
    new Set(['composite-button--primary']),
    new Set(),
  )
  assert.deepEqual(orphans, ['composite-widget--ghost-light-1280.png'])
})

test('findOrphanBaselines still reports an app-prefixed orphan whose route was deleted — the case a blanket `app-*` exemption would have missed', () => {
  const exemptBaselines = loadAppRouteBaselineNames(readFileSync(appRoutesSpecPath, 'utf8'))
  const baselineFiles = [
    ...[...exemptBaselines].map((name) => `${name}.png`),
    // Shaped exactly like a real app-route capture (`app-` prefix, no width segment, optional
    // `-dark` suffix) but naming a route this spec file has never produced — the deleted/renamed
    // case the file's own header calls out.
    'app-signed-in-deleted-route.png',
  ]

  const orphans = findOrphanBaselines(baselineFiles, new Set(), exemptBaselines)
  assert.deepEqual(orphans, ['app-signed-in-deleted-route.png'])
})

test('BASELINE_NAME_RE never matches an app-route capture, so every one of them depends on the exemption rather than the story-id parse', () => {
  assert.equal(BASELINE_NAME_RE.test('app-signed-in-dashboard.png'), false)
  assert.equal(BASELINE_NAME_RE.test('app-signed-in-dashboard-dark.png'), false)
})

test('findIncompleteStories reports every missing {theme, width} unit for a story with no baselines at all', () => {
  const incomplete = findIncompleteStories(new Set(['composite-widget--ghost']), new Set())
  assert.equal(incomplete.length, 1)
  assert.equal(incomplete[0].missingUnits.length, 6)
})

test('findIncompleteStories is silent once all six units exist', () => {
  const id = 'composite-widget--ghost'
  const baselineSet = new Set(
    ['light', 'dark'].flatMap((theme) =>
      [375, 768, 1280].map((width) => `${id}-${theme}-${width}.png`),
    ),
  )
  assert.deepEqual(findIncompleteStories(new Set([id]), baselineSet), [])
})
