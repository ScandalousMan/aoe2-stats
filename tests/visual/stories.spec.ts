// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-touched ones) and passes their ids through VISUAL_STORY_IDS. This file
// stays dumb on purpose: it never re-derives scope, it only renders what it is told to.
import { test, expect } from '@playwright/test'

const storyIds: string[] = JSON.parse(process.env.VISUAL_STORY_IDS ?? '[]')

for (const id of storyIds) {
  test(`${id} matches its visual baseline`, async ({ page }) => {
    await page.goto(`/iframe.html?id=${id}&viewMode=story`)
    // Storybook mounts every story under this id; waiting for it removes the render race that
    // would otherwise make the very first screenshot after a baseline change flaky.
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })
    await expect(root).toHaveScreenshot(`${id}.png`)
  })
}
