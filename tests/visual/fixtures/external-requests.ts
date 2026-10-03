// T676 (constitution III): no network call outside `packages/providers`, and no visual suite may
// reach `avatars.steamstatic.com` (`packages/design-system/specs/player-avatar.md` §9 — a baseline
// must not depend on Steam). Populating the route fixtures with players makes that reachable: any
// fixture player carrying an `avatar_hash` makes `PlayerAvatar` request the Steam CDN. Each fixture
// player therefore keeps `avatar_hash: null` (the harness's own rule), `installSteamAvatarStub`
// (`./avatar-stub`) answers the host locally as a backstop, and this guard records *every* request a
// page makes to a host other than the one serving the built application and fails the test naming
// them — stubbed or not. A stub that quietly absorbed a request would otherwise leave "no suite
// reaches Steam" resting on the fixtures alone, with nothing watching.
import { expect, type Page } from '@playwright/test'

export interface ExternalRequestWatch {
  /** Hosts (with the first URL seen for each) requested that are not the application's own. */
  external: () => string[]
  assertNone: (context: string) => void
}

export function watchExternalRequests(page: Page, appOrigin: string): ExternalRequestWatch {
  const appHost = new URL(appOrigin).host
  const seen = new Map<string, string>()
  page.on('request', (request) => {
    const url = request.url()
    // `data:`, `blob:` and `about:` URLs never leave the page.
    if (!/^https?:/i.test(url)) return
    const host = new URL(url).host
    if (host !== appHost && !seen.has(host)) seen.set(host, url)
  })
  return {
    external: () => [...seen.values()],
    assertNone: (context) => {
      expect(
        [...seen.values()],
        `${context}: the page requested a host other than the application's own (${appHost}) — ` +
          `constitution III forbids a visual suite reaching one; a fixture player with an ` +
          `avatar_hash would reach avatars.steamstatic.com`,
      ).toEqual([])
    },
  }
}
