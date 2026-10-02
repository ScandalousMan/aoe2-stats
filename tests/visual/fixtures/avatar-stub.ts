// The Steam avatar CDN stub, factored out to one shared definition (T675, review finding M4(a) on
// PR #105: `tests/visual/state-signal-sweep.spec.ts` claimed to share `stories.spec.ts`'s own
// render behaviour but installed no stub of its own, so `ProfileSummary`'s state stories — fixture
// `avatarHash` — fired a real request to `avatars.steamstatic.com` from a nightly sweep run:
// nondeterministic, and against `packages/design-system/specs/player-avatar.md` §9 "the visual
// baseline must not depend on Steam"). Both `stories.spec.ts` and `state-signal-sweep.spec.ts` call
// `installSteamAvatarStub` rather than each defining their own `page.route` handler — a fixture (or
// the one hash it answers to) written twice goes stale in one copy, the same reasoning
// `story-render.ts`'s own header gives for factoring the settle logic out of `stories.spec.ts`.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import type { Page, Route } from '@playwright/test'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way. This file
// lives one directory deeper than `tests/visual/stories.spec.ts` (`tests/visual/fixtures/`), so the
// walk to the repo root is one segment longer.
const rootDir = path.resolve(__dirname, '..', '..', '..')

// `player-avatar.md` §9 "the visual baseline must not depend on Steam": `PlayerAvatar` builds
// `https://avatars.steamstatic.com/<hash>_full.jpg` itself (that spec §2b), so any story that
// composes a loaded avatar fires a real request to that host unless it is fulfilled locally.
export const STEAM_AVATAR_FIXTURE = readFileSync(
  path.join(rootDir, 'tests/visual/fixtures/steam-avatar.jpg'),
)

// The one hash `PlayerAvatar.stories.tsx` and `ProfileSummary.stories.tsx` both call
// `FIXTURE_HASH` / `FIXTURE_AVATAR_HASH` — a "Loaded" story is only real if it is genuinely a
// loaded image, so this is the only path the stub answers with the fixture above. Everything else
// under this host (`PlayerAvatar`'s `FailedHash` story deliberately builds a URL from a hash the
// CDN would never serve) is answered with a 404, so `onError` still fires and `FailedHash` stays
// pixel-identical to the empty-hash story — the one identity `player-avatar.md` §9 exists to
// prove. A stub that fulfilled every request on this host indiscriminately would make that story
// indistinguishable from `Loaded` and quietly retire the assertion it stands for.
export const STEAM_AVATAR_FIXTURE_PATH = '/0123456789abcdef0123456789abcdef01234567_full.jpg'

// Installed unconditionally, once per test, rather than only on the stories/units known to carry an
// avatar — both callers stay "dumb" about which story needs which stub (`stories.spec.ts`'s own
// header) and never has to learn it; harmless for a page that never hits this host. Every request
// on this host is fulfilled here — never allowed to pass through to the real network — regardless
// of which path it names, which is what makes this a stub rather than a partial interception: a
// request this function does not recognise still gets a definitive (404) response, never silence
// waiting on a real CDN round-trip.
export async function installSteamAvatarStub(page: Page): Promise<void> {
  await page.route('https://avatars.steamstatic.com/**', (route: Route) => {
    const requestUrl = new URL(route.request().url())
    if (requestUrl.pathname === STEAM_AVATAR_FIXTURE_PATH) {
      return route.fulfill({ status: 200, contentType: 'image/jpeg', body: STEAM_AVATAR_FIXTURE })
    }
    return route.fulfill({ status: 404 })
  })
}
