// T719 (constitution III, FR-047, SC-012): no visual suite that renders a story may depend on the
// network. `Tooltip`'s stories used to request `flagcdn.com` on every capture and nothing noticed —
// `watchExternalRequests` (`./external-requests`) was installed by the route suites alone, and the
// nightly determinism pass cannot see it, because its two renders make the same request.
//
// This file is the story suites' side of that guard, in two parts:
//
// 1. `watchStoryRequests` — `watchExternalRequests` with the one exemption the stories need: a
//    request `installSteamAvatarStub` (`./avatar-stub`) answered locally, because the `PlayerAvatar`
//    stories depend on it (`player-avatar.md` §9). The exemption is "the stub's handler answered
//    this URL", not "this is the Steam host": a request to that host on a page the stub is not
//    installed on reaches the real network and is reported. The failure names the story and the host.
//
// 2. `test` — Playwright's `test` with its `page` fixture overridden to install that watch and assert
//    it once the test body has returned. A spec file imports `test` from here instead of from
//    `@playwright/test`, which is the whole of "installing the watch"; `./watched-specs.test.ts`
//    fails any spec under `tests/visual` that loads a story and does not, so a spec added later
//    cannot be left out. Overriding `page` (rather than adding an auto fixture) keeps the watch lazy:
//    a test that takes no `page` — the browserless plants — still starts no browser.
import { test as base } from '@playwright/test'
import type { Page } from '@playwright/test'
import { stubAnswered } from './avatar-stub'
import { watchExternalRequests } from './external-requests'

export interface StoryRequestWatch {
  /** Story ids the page navigated to, in order, without repeats. */
  stories: () => string[]
  /** Throws, naming the stories and each host, when the page requested a host other than the
   * Storybook build's own that the Steam avatar stub did not answer. */
  assertNone: () => void
}

export function watchStoryRequests(page: Page, appOrigin: string): StoryRequestWatch {
  const appHost = new URL(appOrigin).host
  const stories: string[] = []
  page.on('request', (request) => {
    if (!request.isNavigationRequest() || request.frame() !== page.mainFrame()) return
    const url = new URL(request.url())
    const id = url.pathname.endsWith('/iframe.html') ? url.searchParams.get('id') : null
    if (id && !stories.includes(id)) stories.push(id)
  })
  const external = watchExternalRequests(page, appOrigin, {
    exempt: (url) => stubAnswered(page, url),
  })
  return {
    stories: () => [...stories],
    assertNone: () => {
      const requested = external.external()
      if (requested.length === 0) return
      const named = stories.length > 0 ? stories.map((id) => `"${id}"`).join(', ') : '(none loaded)'
      const hosts = requested.map((url) => `${new URL(url).host} (${url})`).join('; ')
      throw new Error(
        `story ${named}: the page requested a host other than the Storybook build's own ` +
          `(${appHost}): ${hosts}. Constitution III forbids a visual baseline depending on the ` +
          `network; serve the asset from /game-assets/ or inline it. Only a request ` +
          `installSteamAvatarStub answered is exempt.`,
      )
    },
  }
}

export const test = base.extend({
  page: async ({ page, baseURL }, use) => {
    if (!baseURL) throw new Error('story-requests: the project sets no baseURL to watch against.')
    const watch = watchStoryRequests(page, baseURL)
    await use(page)
    watch.assertNone()
  },
})

export { expect } from '@playwright/test'
