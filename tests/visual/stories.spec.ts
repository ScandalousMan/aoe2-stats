// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-touched ones) and passes them through VISUAL_STORIES, each entry naming
// its id and whether its subject escapes the story root (a `position: fixed` element, or a
// popover that overflows its trigger's layout box — see run.mjs for why that happens). This file
// stays dumb on purpose: it never re-derives scope or which stories need a full-page capture, it
// only renders what it is told to.
import { test, expect } from '@playwright/test'

interface VisualStory {
  id: string
  fullPage: boolean
}

const stories: VisualStory[] = JSON.parse(process.env.VISUAL_STORIES ?? '[]')

for (const { id, fullPage } of stories) {
  test(`${id} matches its visual baseline`, async ({ page }) => {
    await page.goto(`/iframe.html?id=${id}&viewMode=story`)
    // Storybook mounts every story under this id; waiting for it removes the render race that
    // would otherwise make the very first screenshot after a baseline change flaky.
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })
    if (fullPage) {
      // The story's own subject (a fixed dialog, an open popover) paints outside the root
      // element's layout box, so a screenshot clipped to that element never shows it — this
      // captures the whole page instead.
      await expect(page).toHaveScreenshot(`${id}.png`)
    } else {
      await expect(root).toHaveScreenshot(`${id}.png`)
    }
  })
}
