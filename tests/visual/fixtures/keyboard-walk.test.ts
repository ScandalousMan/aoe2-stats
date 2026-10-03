// Remediation of review finding B2 on PR #102 (T674, `specs/005-design-system-foundations`):
// `route-keyboard.spec.ts` used to assert only `reachedIds.size === candidateCount` — a `Set`,
// which silently drops duplicates and says nothing about whether the walk reached every candidate
// in order. This file plants small static pages (`page.setContent`, no app build and no Storybook
// story needed) that each trip exactly one of `assertFullTabCoverage`'s guards (unstamped
// candidate, step count, duplicates, DOM order) or `assertStopsInsideChrome`'s guard, paired with a
// control that removes only the planted defect — proof each guard actually fires on the case it
// names, and stays silent on the same page once that one thing is fixed. Two further tests plant no
// defect at all: a candidate hidden by a `display: none` ancestor or by its own `visibility:
// hidden`, proving `walkTabOrder`'s own candidate filter excludes each rather than merely proving a
// downstream guard can catch it once mis-included.
//
// A wrap-closes-the-cycle guard used to live here too (PR #102 review finding B2's first
// remediation): it read a `wrapped` flag set only when the walk's own final Tab press returned
// focus to `document.body` before the step budget ran out. It was unreachable at the default
// budget (`candidateCount + 5`): a walk that produces exactly `candidateCount` stops must have hit
// the null branch to stop iterating at all, so `wrapped` was always `true` whenever the step-count
// guard above it had already passed, and always irrelevant whenever it had not. The one test that
// exercised it (`maxSteps: 3` on a 3-button trap page) only proved a *clean* 3-button page fails
// identically at that budget — it never isolated the wrap guard from the step-count guard. Removed;
// a trap that only starts after every candidate has already been reached once now trips the
// step-count guard instead, at the walk's own default budget, below.
import { test, expect } from '@playwright/test'
import { assertFullTabCoverage, assertStopsInsideChrome, walkTabOrder } from './keyboard-walk'

test.describe('keyboard-walk guards, planted pages', () => {
  test('a trap that starts only after every candidate is reached fails the step-count guard', async ({
    page,
  }) => {
    // Three buttons, DOM order a/b/c. The last one's own keydown handler is the trap: it only
    // fires once every candidate has already been focused in turn (the handler is reached by
    // Tabbing *into* c, same as a clean page — the trap is Tabbing *out* of it), refocusing the
    // first button instead of letting focus leave the document. A real infinite loop: left alone,
    // this page would never let focus reach `document.body`.
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

    // The walk's own default budget (candidateCount + 5, no override): it reaches full, unique,
    // in-order coverage in 3 presses, then keeps pressing into the trap for the remaining 5
    // instead of ever seeing focus leave the document — producing more stops than candidates,
    // which is what actually surfaces this trap now that no separate wrap guard exists.
    const result = await walkTabOrder(page)

    // The exact false negative this remediation closes: every element was reached at least once,
    // so a `Set` of reached ids alone would still see size 3 === candidateCount and pass this trap.
    const reachedIds = new Set(result.steps.map((step) => step.kbdId))
    expect(reachedIds.size, 'sanity: a Set-based check alone would have seen full coverage').toBe(3)
    expect(result.steps.length).toBeGreaterThan(3)

    expect(() => assertFullTabCoverage(result, 'trap-after-coverage')).toThrow(
      /the Tab walk produced \d+ stop\(s\) for 3 candidate\(s\)/,
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

  test('the same page with <summary> replaced by a stamped button passes every guard (control for the unstamped-summary case above)', async ({
    page,
  }) => {
    // Same three-tab-stop shape as the unstamped-summary page above, with the one element
    // `FOCUSABLE_SELECTOR` cannot stamp swapped for one it can — isolates that gap as what actually
    // trips the guard there, not the page's element count or order.
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.steps.every((step) => step.kbdId !== null)).toBe(true)
    expect(() => assertFullTabCoverage(result, 'unstamped-summary-control')).not.toThrow()
  })

  test('a redirect-and-skip combo trips the no-duplicates guard, not the step-count guard', async ({
    page,
  }) => {
    // Five buttons, DOM order a..e. Two independent anomalies, engineered so the *total* step
    // count still equals candidateCount — the step-count guard alone cannot see anything wrong
    // here, isolating the duplicates guard as the one that actually fires:
    // - b's own `focus` handler redirects to a exactly once (one-shot) — one extra visit of a.
    // - c's own `keydown` handler intercepts Tab and refocuses e directly, so d is never visited
    //   at all — one visit short.
    // The extra visit and the missing one cancel out in the total, which is exactly why a bare
    // `reachedIds.size === candidateCount` check (this remediation's own starting point, PR #102
    // review finding B2) is not what is asserted below: it would see 4 unique ids out of 5
    // candidates and reject this page too, but for the wrong reason. This test pins the message
    // actually asserted, not merely that *some* guard rejects.
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
      <button id="d">D</button>
      <button id="e">E</button>
      <script>
        let redirected = false
        document.getElementById('b').addEventListener('focus', () => {
          if (!redirected) {
            redirected = true
            document.getElementById('a').focus()
          }
        })
        document.getElementById('c').addEventListener('keydown', (event) => {
          if (event.key === 'Tab' && !event.shiftKey) {
            event.preventDefault()
            document.getElementById('e').focus()
          }
        })
      </script>
    `)

    const result = await walkTabOrder(page)

    expect(result.steps).toHaveLength(5)
    const ids = result.steps.map((step) => step.kbdId)
    expect(ids).toEqual(['0', '0', '1', '2', '4']) // a, a (redirected), b, c, e — d never reached

    expect(() => assertFullTabCoverage(result, 'redirect-and-skip')).toThrow(
      /reached the same element more than once: #0 \(2x\)/,
    )
  })

  test('the same five buttons without either handler pass every guard', async ({ page }) => {
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
      <button id="d">D</button>
      <button id="e">E</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.steps.map((step) => step.kbdId)).toEqual(['0', '1', '2', '3', '4'])
    expect(() => assertFullTabCoverage(result, 'redirect-and-skip-control')).not.toThrow()
  })

  // T676: a scenario's `prepare` (a search submitted from its input, a menu opened from its trigger)
  // leaves focus somewhere mid-page, and `blur()` alone leaves Chromium's sequential focus
  // navigation starting point there — the next Tab continued from it and `/search (results
  // submitted)` walked 5 stops for 14 candidates. The walk must start at the top whatever had focus.
  test('a walk begun with focus already mid-page still starts at the top', async ({ page }) => {
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
    `)
    await page.focus('#c')

    const result = await walkTabOrder(page)

    expect(result.steps.map((step) => step.kbdId)).toEqual(['0', '1', '2'])
    expect(() => assertFullTabCoverage(result, 'prior-focus')).not.toThrow()
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

    // Full coverage, no duplicates — only the order is wrong, isolating this guard.
    expect(result.steps).toHaveLength(3)
    expect(result.steps.map((step) => step.kbdId)).toEqual(['1', '0', '2']) // b, a, c in DOM-id terms

    expect(() => assertFullTabCoverage(result, 'out-of-dom-order')).toThrow(
      /reached candidates out of DOM order/,
    )
  })

  test("a clean page passes every guard, and doubles as the trap test's control", async ({
    page,
  }) => {
    // Same three buttons as the trap-after-coverage page above, minus the keydown handler — the
    // paired control proving the step-count guard's failure there comes from the trap, not from
    // walking three plain buttons at the default budget.
    await page.setContent(`
      <button id="a">A</button>
      <button id="b">B</button>
      <button id="c">C</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.steps.map((step) => step.kbdId)).toEqual(['0', '1', '2'])
    expect(() => assertFullTabCoverage(result, 'clean-page')).not.toThrow()
  })

  test('a button inside a display:none ancestor is not counted as a candidate', async ({
    page,
  }) => {
    // PR #102 remediation: the old filter read only the element's own `display`/`visibility`, so
    // a button inside a hidden *ancestor* (its own computed style declares neither) was still
    // stamped as a candidate the walk could never actually Tab to. Before this fix, this exact
    // page produced `candidateCount === 3`, `steps.length === 2` (only the two real buttons), and
    // `assertFullTabCoverage` failed with "the Tab walk produced 2 stop(s) for 3 candidate(s)" —
    // blaming the wrong mechanism (a trap or a duplicate) for what was really an over-counted,
    // unreachable candidate. `checkVisibility()` walks the whole ancestor chain instead, so the
    // hidden button is never stamped and the walk passes.
    await page.setContent(`
      <button id="a">A</button>
      <div style="display: none"><button id="hidden">Hidden</button></div>
      <button id="b">B</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.candidateCount).toBe(2)
    expect(result.steps).toHaveLength(2)
    expect(() => assertFullTabCoverage(result, 'hidden-ancestor')).not.toThrow()
  })

  test('a button with its own visibility:hidden is not counted as a candidate', async ({
    page,
  }) => {
    // The candidate filter's own comment explains why `visibilityProperty: true` is required, not
    // the option-less default: `checkVisibility()` alone checks `display` but not `visibility`, so
    // a button declaring `visibility: hidden` on itself (not merely inheriting it from a hidden
    // ancestor, the case above) would be wrongly readmitted as a candidate the walk could never
    // actually Tab to.
    await page.setContent(`
      <button id="a">A</button>
      <button id="hidden" style="visibility: hidden">Hidden</button>
      <button id="b">B</button>
    `)

    const result = await walkTabOrder(page)

    expect(result.candidateCount).toBe(2)
    expect(result.steps).toHaveLength(2)
    expect(() => assertFullTabCoverage(result, 'visibility-hidden')).not.toThrow()
  })

  test('a focusable element outside main/header/footer fails the inside-chrome guard', async ({
    page,
  }) => {
    // FR-049's "no trap outside a modal surface that defines its own", read the cheap way: a
    // route-level walk never opens a modal, so every reachable element must sit inside the route's
    // one `main` landmark or its `header`/`footer` chrome. This check used to live only inline in
    // `route-keyboard.spec.ts`, with no planted-page guard test ever exercising it.
    await page.setContent(`
      <main><button id="a">A</button></main>
      <button id="rogue">Rogue</button>
    `)

    const result = await walkTabOrder(page)

    expect(() => assertStopsInsideChrome(result.steps, 'outside-chrome')).toThrow(
      /outside main\/header\/footer/,
    )
  })

  test('the same rogue button moved inside <main> passes the inside-chrome guard', async ({
    page,
  }) => {
    await page.setContent(`
      <main>
        <button id="a">A</button>
        <button id="rogue">Rogue</button>
      </main>
    `)

    const result = await walkTabOrder(page)

    expect(() => assertStopsInsideChrome(result.steps, 'inside-chrome-control')).not.toThrow()
  })

  // PR #102 review finding (low): the touch-footprint `rect` used to special-case only an `<input>`
  // wrapped by its own `<label>`; generalised to every labelable control a `<label>` can wrap
  // (`input`, `select`, `textarea`, `button`, `meter`, `output`, `progress`) — this plants the
  // `<select>` case, the first of those never exercised before.
  test('a <select> wrapped by its own <label> is measured by the label box, not the bare control', async ({
    page,
  }) => {
    await page.setContent(`
      <label style="display: inline-block; padding: 20px; border: 1px solid black;">
        Country
        <select id="country"><option>FR</option></select>
      </label>
    `)

    const bareSelectWidth = await page
      .locator('#country')
      .evaluate((el) => el.getBoundingClientRect().width)

    const result = await walkTabOrder(page)
    expect(result.steps).toHaveLength(1)
    const [step] = result.steps
    expect(step.tag).toBe('select')
    // The wrapping <label>'s own box (padding included) is the real hit area a pointer reaches —
    // strictly larger than the bare <select> alone, which is what the pre-remediation, `<input>`-
    // only special case would have measured here instead.
    expect(step.rect.width).toBeGreaterThan(bareSelectWidth)
  })
})
