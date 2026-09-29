// Remediation of review finding B4 on PR #102 (T674, `specs/005-design-system-foundations`): no
// prior run showed `assertTouchFootprint` (nor `route-touch-footprint.spec.ts` before this file
// existed) fail on a genuine defect. This file plants small static pages (`page.setContent`, no app
// build and no Storybook story needed — the same pattern `keyboard-walk.test.ts` uses) that each
// trip the 44×44 floor or its one exemption exactly as `packages/design-system/specs/README.md`'s
// "Minimum interactive footprint" describes it, proving the assertion actually fires rather than
// merely existing.
import { test, expect } from '@playwright/test'
import { assertTouchFootprint } from './touch-footprint'

test.describe('touch-footprint assertion, planted pages', () => {
  test('a 40px-tall button fails, naming it', async ({ page }) => {
    await page.setContent(`
      <button
        id="too-short"
        style="box-sizing: border-box; width: 44px; height: 40px; padding: 0; border: 0; margin: 0;"
      >Too Short</button>
    `)

    await expect(assertTouchFootprint(page, 'planted')).rejects.toThrow(
      /<button> "Too Short" is 40\.0px tall, below the 44px floor/,
    )
  })

  test('a 44×30 anchor with no data-variant, inside prose, fails (no marker, no exemption)', async ({
    page,
  }) => {
    await page.setContent(`
      <p>
        Some introductory prose before the link,
        <a
          id="bare-link"
          href="#"
          style="box-sizing: border-box; display: inline-block; width: 44px; height: 30px; padding: 0; border: 0; margin: 0;"
        >Bare Link</a>
        and more prose after it so the anchor is not the only text in its parent.
      </p>
    `)

    await expect(assertTouchFootprint(page, 'planted')).rejects.toThrow(
      /<a> "Bare Link" is 30\.0px tall, below the 44px floor/,
    )
  })

  test('a data-variant="inline" anchor standing alone in its parent fails (standalone misuse)', async ({
    page,
  }) => {
    // The anchor is the *only* text its parent carries — `parentText.length > ownText.length` is
    // false, so `walkTabOrder`'s own `exemptInlineLink` computation (the one and only place this
    // exemption is read from) does not exempt it, exactly as `specs/README.md` describes: "a
    // standalone link whose call site forgot `variant="standalone"` fails, and the failure names
    // the fix."
    await page.setContent(`
      <p><a
        id="standalone-misuse"
        data-variant="inline"
        href="#"
        style="box-sizing: border-box; display: inline-block; width: 44px; height: 20px; padding: 0; border: 0; margin: 0;"
      >Standalone Misuse</a></p>
    `)

    await expect(assertTouchFootprint(page, 'planted')).rejects.toThrow(
      /<a> "Standalone Misuse" is 20\.0px tall, below the 44px floor/,
    )
  })

  test('three passing controls: exempt inline link in a longer sentence, a 44×44 button, and a label-wrapped input', async ({
    page,
  }) => {
    await page.setContent(`
      <p>
        This sentence is deliberately longer than the link it contains, so the
        <a
          id="exempt-inline"
          data-variant="inline"
          href="#"
          style="box-sizing: border-box; display: inline-block; width: 10px; height: 10px; padding: 0; border: 0; margin: 0;"
        >link</a>
        stays exempt from the floor entirely.
      </p>
      <button
        id="ok-button"
        style="box-sizing: border-box; width: 44px; height: 44px; padding: 0; border: 0; margin: 0;"
      >OK</button>
      <label
        id="ok-label"
        style="box-sizing: border-box; display: inline-block; width: 44px; height: 44px; padding: 0; border: 0; margin: 0;"
      >
        Name
        <input
          type="text"
          style="box-sizing: border-box; width: 10px; height: 10px; padding: 0; border: 0; margin: 0;"
        />
      </label>
    `)

    await expect(assertTouchFootprint(page, 'planted')).resolves.not.toThrow()
  })
})
