// T675 slice 4c: unit tests for `resolveClipPartRect` (`story-render.ts`) — the one piece of
// `resolveCaptureClip`'s own clip-part resolution that touches no DOM at all, so it is provable
// against synthetic rects alone, with no browser, no fixture and no story. Every `test()` below
// takes no argument (never `{ page }`/`{ context }`), which is what keeps Playwright from lazily
// spinning up a browser context for it — the same fixture-less idiom the rest of this file's own
// suite reaches for whenever a check has nothing to do with a real page.
import { test, expect } from '@playwright/test'
import { resolveClipPartRect } from './story-render'
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
