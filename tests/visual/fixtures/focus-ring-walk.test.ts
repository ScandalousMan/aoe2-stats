// Remediation of review finding M1 (this is also finding B4 for focus visibility: "no suite has
// been seen red") on PR #102 (T674, `specs/005-design-system-foundations`): `route-focus-
// visibility.spec.ts`'s per-step assertion (a) never checked outline *width*, so a 0px or 1px ring
// passed the same as a real one, (b) resolved the background a ring is judged against starting from
// the focused element itself — wrong for an outward-offset ring (`outline-offset` > 0), which is
// painted over the PARENT's surface, not the element's own — and (c) treated a translucent
// background (alpha < 1) as opaque the instant it was merely non-zero, reading its raw channel
// values instead of compositing it over what is actually behind it. This file plants small static
// pages (`page.setContent`, no app build and no Storybook story needed) that each trip one of those
// gaps, plus one clean page that trips none of them — proof each check actually fires rather than
// merely existing, following the pattern `tests/visual/fixtures/keyboard-walk.test.ts` already uses
// for `assertFullTabCoverage`.
import { test, expect } from '@playwright/test'
import { contrastRatioRgb } from '../../../packages/design-system/tokens/contrast.mjs'
import { assertFocusRingVisible, parseRgb, walkTabOrder } from './keyboard-walk'

test.describe('focus-ring-visible guard, planted pages', () => {
  test('a clean ring on an opaque background passes every check', async ({ page }) => {
    await page.setContent(`
      <button id="a" style="background: white; outline: 2px solid black;">A</button>
    `)

    const { steps } = await walkTabOrder(page)
    expect(steps).toHaveLength(1)
    const [step] = steps

    expect(step.isFocusVisible).toBe(true)
    expect(step.outline.style).not.toBe('none')
    expect(step.outline.width).toBe('2px')
    expect(() => assertFocusRingVisible(step, 'clean-control')).not.toThrow()
  })

  test('outline: none fails the "painted a ring" check', async ({ page }) => {
    await page.setContent(`
      <button id="a" style="background: white; outline: none;">A</button>
    `)

    const { steps } = await walkTabOrder(page)
    expect(steps).toHaveLength(1)
    const [step] = steps

    expect(step.isFocusVisible, 'the button is still reached and focus-visible').toBe(true)
    expect(step.outline.style).toBe('none')
    expect(() => assertFocusRingVisible(step, 'outline-none')).toThrow(
      /painted no outline while focus-visible/,
    )
  })

  test('a 1px ring fails the width check the pre-remediation assertion never made', async ({
    page,
  }) => {
    await page.setContent(`
      <button id="a" style="background: white; outline: 1px solid black;">A</button>
    `)

    const { steps } = await walkTabOrder(page)
    expect(steps).toHaveLength(1)
    const [step] = steps
    expect(step.outline.width).toBe('1px')

    // Sanity: the pre-remediation assertion (`route-focus-visibility.spec.ts` before M1) only
    // checked `isFocusVisible`, `outline.style !== 'none'` and the 3:1 contrast ratio — never the
    // width — so it would have passed this 1px ring exactly like a real 2px one.
    expect(step.isFocusVisible).toBe(true)
    expect(step.outline.style).not.toBe('none')
    const oldRatio = contrastRatioRgb(parseRgb(step.outline.color), parseRgb(step.backgroundColor))
    expect(
      oldRatio,
      'sanity: the old, width-blind assertion would have seen sufficient contrast here too',
    ).toBeGreaterThanOrEqual(3)

    // The new guard catches what the old one could not: the ring is real, but too thin.
    expect(() => assertFocusRingVisible(step, 'outline-1px')).toThrow(/is 1px wide, not the 2px/)
  })

  test("an outward-offset ring judged against its own background instead of its parent's fails the contrast check", async ({
    page,
  }) => {
    // The outward-offset bug (M1): the button's OWN background (#cccccc) contrasts fine against a
    // black ring, but the ring is offset 4px outward, so it is actually painted over the parent
    // <div>'s dark surface (#333333) instead — a real keyboard user sees the ring on that dark
    // surface, where it does not clear 3:1.
    await page.setContent(`
      <div style="background: #333333; padding: 40px;">
        <button id="a" style="background: #cccccc; outline: 2px solid black; outline-offset: 4px;">A</button>
      </div>
    `)

    const { steps } = await walkTabOrder(page)
    expect(steps).toHaveLength(1)
    const [step] = steps

    // Sanity: the pre-remediation background walk started at the element itself and would have
    // stopped on the button's own opaque background, never reaching the parent the ring is actually
    // painted over.
    const ownBackground = await page
      .locator('#a')
      .evaluate((el) => getComputedStyle(el).backgroundColor)
    const oldRatio = contrastRatioRgb(parseRgb(step.outline.color), parseRgb(ownBackground))
    expect(
      oldRatio,
      "sanity: judged against the element's own background, this ring would have wrongly passed",
    ).toBeGreaterThanOrEqual(3)

    // The new guard resolves the PARENT's surface instead, because `outline-offset` > 0, and fails
    // correctly: the parsed contrast is well under the floor.
    const { r, g, b } = parseRgb(step.backgroundColor)
    expect([r, g, b].every((channel) => Math.abs(channel - 51) <= 2)).toBe(true)
    expect(() => assertFocusRingVisible(step, 'outward-offset-bug')).toThrow(
      /below the 3:1 WCAG 1\.4\.11 non-text contrast floor/,
    )
  })

  test('a ring over a translucent background fails unless alpha is composited, not ignored', async ({
    page,
  }) => {
    // The translucent-background bug (M1): the button's own background is 30%-opacity white over a
    // black parent — a real render shows a dark grey, barely brighter than the black ring, but
    // reading the raw `rgba(255, 255, 255, 0.3)` channel values while ignoring alpha sees pure white
    // instead, and a black ring against white passes easily.
    await page.setContent(`
      <div style="background: #000000; padding: 40px;">
        <button id="a" style="background: rgba(255, 255, 255, 0.3); outline: 2px solid black;">A</button>
      </div>
    `)

    const { steps } = await walkTabOrder(page)
    expect(steps).toHaveLength(1)
    const [step] = steps

    // Sanity: parsing the raw, uncomposited rgba string and discarding alpha (`parseRgb` only ever
    // reads the first three channels) reproduces the old bug exactly — treating 30%-opacity white as
    // opaque white.
    const ownRawBackground = await page
      .locator('#a')
      .evaluate((el) => getComputedStyle(el).backgroundColor)
    const oldRatio = contrastRatioRgb(parseRgb(step.outline.color), parseRgb(ownRawBackground))
    expect(
      oldRatio,
      'sanity: ignoring alpha and reading the raw rgba string would have wrongly passed',
    ).toBeGreaterThanOrEqual(3)

    // The new guard composites the translucent layer over its opaque parent (30% white over black
    // is a dark grey, ~rgb(77, 77, 77)) and fails correctly: that grey barely clears the black ring.
    const { r, g, b } = parseRgb(step.backgroundColor)
    expect([r, g, b].every((channel) => Math.abs(channel - 77) <= 2)).toBe(true)
    expect(() => assertFocusRingVisible(step, 'translucent-background')).toThrow(
      /below the 3:1 WCAG 1\.4\.11 non-text contrast floor/,
    )
  })
})
