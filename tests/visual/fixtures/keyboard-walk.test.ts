// Remediation of review finding B2 on PR #102 (T674, `specs/005-design-system-foundations`):
// `route-keyboard.spec.ts` used to assert only `reachedIds.size === candidateCount` — a `Set`,
// which silently drops duplicates and says nothing about whether the walk ever closed the cycle.
// This file plants small static pages (`page.setContent`, no app build and no Storybook story
// needed) that each trip exactly one of the four guards `assertFullTabCoverage` now runs, plus one
// clean page that trips none of them — proof each guard actually fires rather than merely existing.
import { test, expect } from '@playwright/test'
import { assertFullTabCoverage, walkTabOrder } from './keyboard-walk'

test.describe('keyboard-walk guards, planted pages', () => {
  test('a trap that starts only after every candidate is reached fails the wrap guard', async ({
    page,
  }) => {
    // Three buttons, DOM order a/b/c. The last one's own keydown handler is the trap: it only
    // fires once every candidate has already been focused in turn (the handler is reached by
    // Tabbing *into* c, same as a clean page — the trap is Tabbing *out* of it), refocusing the
    // first button instead of letting focus leave the document. A real infinite loop: left alone,
    // this page would never wrap.
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
      <script>
        document.getElementById('c').addEventListener('keydown', (event) => {
          if (event.key === 'Tab' && !event.shiftKey) {
            event.preventDefault()
            document.getElementById('a').focus()
          }
        })
      </script>
    `)

    // The default step budget (candidateCount + 5) would run past the point where c's trap starts
    // cycling focus back through a/b/c, producing duplicates that the "no duplicates" guard below
    // would also (correctly) reject — muddying which guard is under test here. Overriding
    // `maxSteps` to exactly `candidateCount` isolates the wrap guard: the walk reaches full, unique,
    // in-order coverage in exactly 3 presses and stops right there, before ever pressing Tab a
    // fourth time to observe whether the cycle would have closed or the trap would have caught it.
    const result = await walkTabOrder(page, 3)

    // The exact false negative this remediation closes: every element was reached exactly once, so
    // the pre-remediation assertion — a `Set` of reached ids — sees size 3 === candidateCount and
    // would have passed this trap.
    const reachedIds = new Set(result.steps.map((step) => step.kbdId))
    expect(reachedIds.size, 'sanity: the old Set-based check would have seen full coverage').toBe(3)
    expect(result.steps).toHaveLength(3)

    // The new guard catches what the old one could not: the walk never saw the cycle close.
    expect(result.wrapped).toBe(false)
    expect(() => assertFullTabCoverage(result, 'trap-after-coverage')).toThrow(
      /used its full step budget without focus ever wrapping/,
    )
  })

  test('an unstamped focusable fails the stamped-candidate guard', async ({ page }) => {
    // `<summary>` is natively a tab stop in Chromium without carrying a `tabindex` attribute, so
    // `FOCUSABLE_SELECTOR` never matches it and it is never stamped with a `data-kbd-walk-id` —
    // exactly the Chromium 130+ scroller/`<summary>` gap the finding names.
    await page.setContent(`
      <button id="a">A</button>
      <details><summary>Menu</summary><div>content</div></details>
      <button id="c">C</button>
    `)

    const result = await walkTabOrder(page)

    const unstamped = result.steps.filter((step) => step.kbdId === null)
    expect(unstamped, 'the <summary> is a real tab stop the walk never stamped').toHaveLength(1)
    expect(unstamped[0].tag).toBe('summary')

    expect(() => assertFullTabCoverage(result, 'unstamped-summary')).toThrow(
      /never stamped as a candidate.*summary/is,
    )
  })

  test('a focus redirect that revisits an element fails the no-duplicates guard', async ({
    page,
  }) => {
    // Three buttons, DOM order a/b/c. Focusing b redirects to a exactly once (a one-shot
    // redirect, not an infinite loop), so the walk still wraps normally at the end — isolating the
    // duplicate from the wrap guard above.
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
      <script>
        let redirected = false
        document.getElementById('b').addEventListener('focus', () => {
          if (!redirected) {
            redirected = true
            document.getElementById('a').focus()
          }
        })
      </script>
    `)

    const result = await walkTabOrder(page)

    expect(result.wrapped, 'the redirect is one-shot, so the walk still closes the cycle').toBe(
      true,
    )
    const ids = result.steps.map((step) => step.kbdId)
    expect(ids.filter((id) => id === '0')).toHaveLength(2) // button a, reached twice

    expect(() => assertFullTabCoverage(result, 'duplicate-landing')).toThrow(
      /stop\(s\) for 3 candidate\(s\)/,
    )
  })

  test('positive tabindex out of DOM order fails the DOM-order guard', async ({ page }) => {
    // This codebase itself never declares a positive `tabindex` (verified by grepping
    // `apps/web/src` and `packages/design-system/src` — every declared `tabindex` there is `"-1"`
    // or `"0"`), so this fixture uses one deliberately, only to prove the guard actually compares
    // order rather than merely counting: DOM order is a, b, c but keyboard order is b, a, c.
    await page.setContent(`
      <button id="a" tabindex="2">A</button>
      <button id="b" tabindex="1">B</button>
      <button id="c" tabindex="3">C</button>
    `)

    const result = await walkTabOrder(page)

    // Full coverage, no duplicates, wraps normally — only the order is wrong, isolating this guard.
    expect(result.wrapped).toBe(true)
    expect(result.steps).toHaveLength(3)
    expect(result.steps.map((step) => step.kbdId)).toEqual(['1', '0', '2']) // b, a, c in DOM-id terms

    expect(() => assertFullTabCoverage(result, 'out-of-dom-order')).toThrow(
      /reached candidates out of DOM order/,
    )
  })

  test('a clean page passes every guard', async ({ page }) => {
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.wrapped).toBe(true)
    expect(result.steps.map((step) => step.kbdId)).toEqual(['0', '1', '2'])
    expect(() => assertFullTabCoverage(result, 'clean-page')).not.toThrow()
  })
})
