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

export interface ExternalRequestOptions {
  /** A request this returns true for is not reported. Asked when `external()` or `assertNone` is
   * called, never when the request is made: the handler that answers a request locally can run
   * after the `request` event fires. Omitted, every request to another host is reported, which is
   * what the route suites need (T676). The story suites pass `stubAnswered` (`./avatar-stub`),
   * T719. */
  exempt?: (url: string) => boolean
}

export function watchExternalRequests(
  page: Page,
  appOrigin: string,
  { exempt }: ExternalRequestOptions = {},
): ExternalRequestWatch {
  const appHost = new URL(appOrigin).host
  const seen = new Map<string, string[]>()
  page.on('request', (request) => {
    const url = request.url()
    // `data:`, `blob:` and `about:` URLs never leave the page.
    if (!/^https?:/i.test(url)) return
    const host = new URL(url).host
    if (host === appHost) return
    seen.set(host, [...(seen.get(host) ?? []), url])
  })
  // The first reported URL of each host, in the order the hosts were first requested.
  const reported = (): string[] =>
    [...seen.values()].flatMap((urls) => urls.filter((url) => !exempt?.(url)).slice(0, 1))
  return {
    external: reported,
    assertNone: (context) => {
      expect(
        reported(),
        `${context}: the page requested a host other than the application's own (${appHost}) — ` +
          `constitution III forbids a visual suite reaching one; a fixture player with an ` +
          `avatar_hash would reach avatars.steamstatic.com`,
      ).toEqual([])
    },
  }
}
