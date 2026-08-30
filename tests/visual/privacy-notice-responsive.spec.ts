// T096 defect 1 regression (visual review, remediated by this change): at a 375px viewport,
// PrivacyNotice's §4.4 storage tables (ProcessorList, OutwardCallList) rendered as real
// three-column `<table>`s and OutwardCallList overflowed the viewport —
// `document.documentElement.scrollWidth` measured 419 against a 375 viewport, a 44px sideways-
// scroll region. privacy-notice.md §8 requires both to stack as one labelled block per row below
// `md` (768px), and §10 forbids horizontal scrolling "in any section, including both tables". This
// is an assertion against live layout, not a screenshot diff: a baseline screenshot only proves a
// regression once one already exists to diff against, and this test must fail on the exact code
// that shipped the bug.
import { test, expect } from '@playwright/test'

const STORY_ID = 'screens-privacynotice--default'

test.describe('PrivacyNotice — §4.4 storage tables at 375 and 768', () => {
  test('at 375: no horizontal overflow, and both tables are stacked as labelled blocks', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 900 })
    await page.goto(`/iframe.html?id=${STORY_ID}&viewMode=story`)
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(scrollWidth).toBeLessThanOrEqual(375)

    // Both tables exist in the DOM (needed at >=768) but are not visible at 375 — `display: none`,
    // not merely scrolled off-screen or clipped, so a screen reader and find-in-page never see two
    // copies of this legal text at once. Scoped to the notice's own `<article>`: Storybook's
    // args-table addon renders its own (aria-hidden, unrelated) `<table>` alongside the story.
    const tables = page.locator('article table')
    await expect(tables).toHaveCount(2)
    for (const table of await tables.all()) {
      await expect(table).toBeHidden()
    }

    // The stacked labelled-block form is present instead: a `<dt>` "Provider" (ProcessorList) and
    // a `<dt>` "Service" (OutwardCallList), each visible — the same `<dl>` pattern CategoryEntry
    // uses, per §8.
    await expect(page.locator('article dt', { hasText: 'Provider' }).first()).toBeVisible()
    await expect(page.locator('article dt', { hasText: 'Service' }).first()).toBeVisible()
  })

  test('at 768: the tabular layout is intact', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 })
    await page.goto(`/iframe.html?id=${STORY_ID}&viewMode=story`)
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(scrollWidth).toBeLessThanOrEqual(768)

    const tables = page.locator('article table')
    await expect(tables).toHaveCount(2)
    for (const table of await tables.all()) {
      await expect(table).toBeVisible()
    }

    // Column headings from both tables prove the tabular (not stacked) form renders here.
    await expect(
      page.locator('article').getByRole('columnheader', { name: 'Provider' }),
    ).toBeVisible()
    await expect(
      page.locator('article').getByRole('columnheader', { name: 'Service' }),
    ).toBeVisible()
  })
})
