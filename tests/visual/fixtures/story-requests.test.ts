// T719: the guard behind "no visual suite that renders a story reaches a host other than the one
// serving the Storybook build", shown failing. Each case plants a page standing in for a story page
// (`/iframe.html?id=...`, fulfilled by a route so no Storybook build is read and nothing leaves the
// machine) and runs it through `watchStoryRequests` / the overridden `test` of `./story-requests`.
import { expect, test as plain } from '@playwright/test'
import { installSteamAvatarStub, STEAM_AVATAR_FIXTURE_PATH } from './avatar-stub'
import { test as watched, watchStoryRequests } from './story-requests'

const STORY_ID = 'planted-story--default'
const AVATAR_URL = `https://avatars.steamstatic.com${STEAM_AVATAR_FIXTURE_PATH}`

// Fulfils `<origin>/iframe.html` with one `<img>` and settles once the image has finished.
async function loadPlantedStory(
  page: import('@playwright/test').Page,
  origin: string,
  imageUrl: string,
): Promise<void> {
  await page.route(`${origin}/iframe.html**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: `<html><body><img id="planted" alt="" src="${imageUrl}"></body></html>`,
    }),
  )
  await page.goto(`${origin}/iframe.html?id=${STORY_ID}&viewMode=story`)
  await page.waitForFunction(
    () => (document.getElementById('planted') as HTMLImageElement).complete,
  )
}

plain.describe('story-request guard, planted story pages', () => {
  plain(
    'plant: a story page carrying an image on a foreign host fails, naming the story and the host',
    async ({ page, baseURL }) => {
      // The host is answered locally by a route that is *not* the Steam stub: the request is still
      // made, and still reported.
      await page.route('https://cdn.example.invalid/**', (route) =>
        route.fulfill({ status: 200, contentType: 'image/gif', body: '' }),
      )
      const watch = watchStoryRequests(page, baseURL!)
      await loadPlantedStory(page, baseURL!, 'https://cdn.example.invalid/flag.png')

      expect(() => watch.assertNone()).toThrow(
        new RegExp(
          `story "${STORY_ID}".*cdn\\.example\\.invalid \\(https://cdn\\.example\\.invalid/flag\\.png\\)`,
        ),
      )
    },
  )

  plain(
    'plant: a request to the avatar host with the stub absent fails, naming the host',
    async ({ page, baseURL }) => {
      // Aborted so nothing reaches the real CDN; an abort is not the stub, and does not exempt.
      await page.route('https://avatars.steamstatic.com/**', (route) => route.abort())
      const watch = watchStoryRequests(page, baseURL!)
      await loadPlantedStory(page, baseURL!, AVATAR_URL)

      expect(() => watch.assertNone()).toThrow(/avatars\.steamstatic\.com/)
    },
  )

  plain(
    'contrast: a story page whose only foreign request is the stubbed avatar passes',
    async ({ page, baseURL }) => {
      await installSteamAvatarStub(page)
      const watch = watchStoryRequests(page, baseURL!)
      await loadPlantedStory(page, baseURL!, AVATAR_URL)

      watch.assertNone()
      expect(watch.stories()).toEqual([STORY_ID])
    },
  )

  plain(
    'contrast: a story page with only its own origin and data: content passes',
    async ({ page, baseURL }) => {
      const watch = watchStoryRequests(page, baseURL!)
      await loadPlantedStory(page, baseURL!, 'data:image/gif;base64,R0lGODlhAQABAAAAACw=')

      watch.assertNone()
    },
  )
})

// The overridden `test` is what the story suites actually run under: this case proves the teardown
// assertion fires, through the fixture and not through a hand-called `assertNone`. `test.fail()` is
// the strict expected-failure of this runner — it passes only if the test body below ends in an
// error, and fails the suite if the fixture lets a foreign image through.
watched(
  'plant: the overridden test fixture fails a test whose story page requested a foreign host',
  async ({ page, baseURL }) => {
    watched.fail()
    await page.route('https://cdn.example.invalid/**', (route) =>
      route.fulfill({ status: 200, contentType: 'image/gif', body: '' }),
    )
    await loadPlantedStory(page, baseURL!, 'https://cdn.example.invalid/flag.png')
  },
)

watched(
  'contrast: the overridden test fixture passes a test whose only foreign request is the stubbed avatar',
  async ({ page, baseURL }) => {
    await installSteamAvatarStub(page)
    await loadPlantedStory(page, baseURL!, AVATAR_URL)
  },
)
