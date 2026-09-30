// T675 slice 4c: unit tests for `resolveClipPartRect` (`story-render.ts`) — the one piece of
// `resolveCaptureClip`'s own clip-part resolution that touches no DOM at all, so it is provable
// against synthetic rects alone, with no browser, no fixture and no story. Every `test()` below
// takes no argument (never `{ page }`/`{ context }`), which is what keeps Playwright from lazily
// spinning up a browser context for it — the same fixture-less idiom the rest of this file's own
// suite reaches for whenever a check has nothing to do with a real page.
import { test, expect } from '@playwright/test'
import { resolveClipPartRect, resolveCaptureClip } from './story-render'
import type { EdgeRect } from './story-render'

const boundingRect: EdgeRect = { left: 10, top: 20, right: 110, bottom: 40 }

test('resolveClipPartRect: fragment undefined returns the bounding box unchanged — every clip part before this option existed', () => {
  const clientRects: EdgeRect[] = [
    { left: 10, top: 20, right: 60, bottom: 30 },
    { left: 10, top: 30, right: 110, bottom: 40 },
  ]
  expect(resolveClipPartRect(undefined, boundingRect, clientRects)).toEqual(boundingRect)
})

test('resolveClipPartRect: fragment "first" on a wrapped inline element returns only its own first line', () => {
  // A two-word inline link wrapped across two lines at a narrow viewport — the shape T675 slice 4c
  // exists for: the bounding box spans both lines (110×20), the first client rect is only the
  // first line's own run (50×10), a quarter of the bounding box's own area.
  const firstLine: EdgeRect = { left: 10, top: 20, right: 60, bottom: 30 }
  const secondLine: EdgeRect = { left: 10, top: 30, right: 110, bottom: 40 }
  const wrapped: EdgeRect = { left: 10, top: 20, right: 110, bottom: 40 }
  expect(resolveClipPartRect('first', wrapped, [firstLine, secondLine])).toEqual(firstLine)
})

test('resolveClipPartRect: fragment "first" on a single-fragment element is a no-op — the unwrapped case every existing clip target is', () => {
  // `getClientRects()` on an element that never wraps reports exactly one rect, identical to
  // `getBoundingClientRect()` — the property that makes `fragment: 'first'` safe to add to a clip
  // part without first checking whether that part's own target ever wraps.
  expect(resolveClipPartRect('first', boundingRect, [boundingRect])).toEqual(boundingRect)
})

test('resolveClipPartRect: fragment "first" falls back to the bounding box when the element reports no client rects', () => {
  expect(resolveClipPartRect('first', boundingRect, [])).toEqual(boundingRect)
})

test('resolveClipPartRect: an unrecognised fragment value throws rather than silently returning the bounding box', () => {
  expect(() =>
    // @ts-expect-error — deliberately not the one value `VisualCaptureClipPart['fragment']` allows,
    // proving the runtime guard fires even though the type system would already catch this in a
    // real story file; a config or a test double is not always type-checked before it runs.
    resolveClipPartRect('Last', boundingRect, [boundingRect]),
  ).toThrow(/unrecognised "fragment" value/)
})

// T675 H1 remediation (reviewer finding on PR #105): `resolveCaptureClip` used to union in EVERY
// named part's own rect unconditionally, including a part that carries no box at all — the exact
// shape `Tooltip`'s own surface is at rest (`<span role="tooltip" hidden={!isOpen}>`,
// `packages/design-system/src/primitives/Tooltip/index.tsx`, always in the DOM). A `display: none`
// element's `getBoundingClientRect()` collapses to (0, 0, 0, 0) — the page origin, not the
// element's own layout position, because it has no layout position — so unioning it in dragged the
// whole clip's top-left corner to (0, 0) and inflated its width/height to reach the button from
// there, 7 of the T675 sweep's 8 `dimension-mismatch` flags. These three tests plant a page with
// `page.setContent` (no app build, no Storybook story — `fixtures/touch-footprint.test.ts`'s own
// pattern) rather than going through a real story, so the union math is provable without a browser
// render pipeline in the way. `--ds-space-0: 0px` plus `pad: '0'` on every clip below keeps the
// expected rect arithmetic free of `resolvePadPx`'s own token lookup.
test.describe('resolveCaptureClip: an unrendered part never drags the union to the page origin (T675 H1)', () => {
  const plantedPage = `
    <!doctype html>
    <html>
      <head>
        <style>
          :root { --ds-space-0: 0px; }
          body { margin: 0; padding: 0; }
          #trigger {
            position: absolute; left: 10px; top: 20px; width: 44px; height: 44px;
            box-sizing: border-box; margin: 0; padding: 0; border: 0;
          }
          #surface {
            position: absolute; left: 10px; top: 80px; width: 120px; height: 30px;
            box-sizing: border-box; margin: 0; padding: 0; border: 0;
          }
        </style>
      </head>
      <body>
        <button id="trigger">Hover me</button>
        <span id="surface" role="tooltip">Tooltip text</span>
      </body>
    </html>
  `

  test('a clip over [button, hidden 0x0 tooltip span] resolves to the button rect alone, not the origin-dragged union', async ({
    page,
  }) => {
    await page.setContent(plantedPage)
    // `hidden` (not `visibility: hidden`) is `Tooltip`'s own resting shape — the attribute the UA
    // stylesheet turns into `display: none`, so the element reports no box at all.
    await page.locator('#surface').evaluate((el) => el.setAttribute('hidden', ''))

    const rect = await resolveCaptureClip(page, page.locator('body'), 'planted', {
      parts: [{ role: 'button' }, { selector: '[role="tooltip"]' }],
      pad: '0',
    })

    // Fixed behaviour: the hidden tooltip span contributes nothing, so the clip is the button's own
    // rect alone (10, 20, 44x44).
    //
    // Run against the pre-fix code (reverting just the `isClipPartRendered` gate in
    // `resolveCaptureClip`, confirmed by actually doing so and re-running this test before writing
    // the fix), this same assertion received:
    //   { x: 0, y: 0, width: 54, height: 64 } — left/top dragged to the page origin by the hidden
    //   span's (0,0,0,0) `getBoundingClientRect()`, right/bottom still reaching the button's own
    //   edges (54 = 10 + 44, 64 = 20 + 44) because `Math.max` with 0 never shrinks them. That is the
    //   exact shape H1 (PR #105) reported: 7 of the T675 sweep's 8 `dimension-mismatch` flags.
    expect(rect).toEqual({ x: 10, y: 20, width: 44, height: 44 })
  })

  test('CONTROL: the same clip with the tooltip open (visible) resolves to the union of both parts', async ({
    page,
  }) => {
    await page.setContent(plantedPage)
    // No `hidden` attribute set — the tooltip span renders at its own planted box (10, 80, 120x30).

    const rect = await resolveCaptureClip(page, page.locator('body'), 'planted', {
      parts: [{ role: 'button' }, { selector: '[role="tooltip"]' }],
      pad: '0',
    })

    // Union of (10,20)-(54,64) and (10,80)-(130,110): left=10, top=20, right=130, bottom=110 — a
    // real, legitimate size difference from the RED case above (the state the button/tooltip pair
    // is actually testing), not the origin-drag bug that case used to show.
    expect(rect).toEqual({ x: 10, y: 20, width: 120, height: 90 })
  })

  test('a `visibility: hidden` part is ignored the same way a `display: none` one is', async ({
    page,
  }) => {
    await page.setContent(plantedPage)
    // `visibility: hidden` keeps the element's own box (unlike `display: none`) but paints nothing
    // — `checkVisibility({ visibilityProperty: true })` is what catches this case; a zero-area check
    // alone would have missed it, since this span's box is not zero-area.
    await page.locator('#surface').evaluate((el) => {
      ;(el as HTMLElement).style.visibility = 'hidden'
    })

    const rect = await resolveCaptureClip(page, page.locator('body'), 'planted', {
      parts: [{ role: 'button' }, { selector: '[role="tooltip"]' }],
      pad: '0',
    })

    expect(rect).toEqual({ x: 10, y: 20, width: 44, height: 44 })
  })
})
