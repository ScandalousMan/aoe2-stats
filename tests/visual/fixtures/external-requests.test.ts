// T676 (constitution III): the guard behind "no suite reaches avatars.steamstatic.com", shown
// failing. Where a suite asserts "no X reached", the absence case has to be planted: here a page
// whose `<img>` points at the Steam CDN — with `installSteamAvatarStub` installed, exactly as every
// route scenario installs it — must still trip the guard, because the stub answers the request but
// does not stop it having been made.
import { expect, test } from '@playwright/test'
import { installSteamAvatarStub, STEAM_AVATAR_FIXTURE_PATH } from './avatar-stub'
import { watchExternalRequests } from './external-requests'

const APP_ORIGIN = 'http://127.0.0.1:4999'

test.describe('external-request guard, planted pages', () => {
  test('a page requesting the Steam CDN fails the guard even though the stub answers it', async ({
    page,
  }) => {
    await installSteamAvatarStub(page)
    const external = watchExternalRequests(page, APP_ORIGIN)

    await page.setContent(
      `<img id="avatar" alt="" src="https://avatars.steamstatic.com${STEAM_AVATAR_FIXTURE_PATH}">`,
    )
    await page.waitForFunction(
      () => (document.getElementById('avatar') as HTMLImageElement).complete,
    )

    expect(() => external.assertNone('planted')).toThrow(
      /requested a host other than the application's own \(127\.0\.0\.1:4999\)/,
    )
    expect(external.external()).toEqual([
      `https://avatars.steamstatic.com${STEAM_AVATAR_FIXTURE_PATH}`,
    ])
  })

  test('control: a page with only inline and data: content passes the guard', async ({ page }) => {
    const external = watchExternalRequests(page, APP_ORIGIN)

    await page.setContent(`<img alt="" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">`)
    await page.waitForLoadState()

    external.assertNone('planted')
  })
})
