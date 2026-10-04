// Factored out of `tests/visual/stories.spec.ts` (T675, slice 1/N) — behaviour-preserving: every
// function below is the exact code that used to live inline in that file's own per-unit test body,
// moved here unchanged so `tests/visual/state-signal-sweep.spec.ts` can drive the same settle logic,
// theme mechanism, force-state application and clip resolution without a second copy of any of it
// (this task's own instruction: "import or factor out, do not copy — a fact written twice goes
// stale in one copy"). `stories.spec.ts` now imports these instead of defining them; nothing about
// what it asserts, waits for or captures changed.
import type { Locator, Page } from '@playwright/test'

export type Theme = 'light' | 'dark'

// T565 (FR-047's own remediation) and T591 — see the extended comment history in git blame for the
// empirical measurements behind exactly which of `.hover()`/`page.mouse.down()`/`.focus()` matches
// each real CSS pseudo-class in Chromium, and why: this file only carries the resulting shapes.
export interface VisualForceState {
  state: 'hover' | 'active' | 'focus-visible'
  selector?: string
  role?: string
  name?: string
  nth?: number
}

// A clip part locates one element (`selector`, or `role` optionally narrowed by `name`; `nth`
// breaks a tie when either matches more than one — `locateClipPart` below throws otherwise) and
// contributes its own rect to the union `resolveCaptureClip` clips to, inflated by `pad` (a
// `tokens/space.json` step name; `resolveCaptureClip`'s own default is `'2'`).
//
// `fragment` (T675 slice 4c) — omitted, the default for every clip part before this option
// existed — takes the element's full *bounding box*, spanning every line an inline element wraps
// across at a narrow viewport. `fragment: 'first'` takes its own *first client rect*
// (`getClientRects()[0]`) instead: one line, the one carrying the underline, whatever the
// container's width — a real fix for an inline `Link` inside running prose, where the bounding box
// at 375px can be several times the area of the same element unwrapped at 1280px, diluting a real,
// present signal under the comparator's own `maxDiffPixelRatio` floor for no reason connected to
// the signal itself (T675's slice 4c, for the `ThirdPartyObjectionForm`/`Link` `inline`
// residuals the sweep measured). A no-op for anything
// that lays out as a single fragment — `getClientRects()` then reports exactly one rect, identical
// to the bounding box — so it is safe to add without checking a target's own layout first. Opt-in,
// on the stories that measurably need it, never global: `resolveClipPartRect`'s own tests cover the
// wrapped-vs-unwrapped shapes without a browser; the sweep and `stories.spec.ts`'s own committed
// baselines are the coverage for the real, rendered case, since both share this one resolver.
export interface VisualCaptureClipPart {
  selector?: string
  role?: string
  name?: string
  nth?: number
  fragment?: 'first'
}

export interface VisualCaptureClip {
  parts: VisualCaptureClipPart[]
  pad?: string
}

// Reads the settled story's own `parameters.visualForceState` from
// `window.__STORYBOOK_PREVIEW__.storyRenders` — the same render-record lookup `waitForStorySettled`
// below already uses to learn a story's render `phase`, asked one more question. `null` for every
// story that carries none, which is nearly all of them.
export async function readForceState(
  page: Page,
  storyId: string,
): Promise<VisualForceState | null> {
  return page.evaluate((id: string) => {
    const preview = (
      window as unknown as {
        __STORYBOOK_PREVIEW__?: {
          storyRenders?: { id: string; story?: { parameters?: Record<string, unknown> } }[]
        }
      }
    ).__STORYBOOK_PREVIEW__
    const render = preview?.storyRenders?.find((r) => r.id === id)
    const forced = render?.story?.parameters?.visualForceState
    return (forced ?? null) as VisualForceState | null
  }, storyId)
}

// T591: reads `parameters.visualCaptureClip` the same way. `null` for every story that carries
// none, which is nearly all of them.
export async function readCaptureClip(
  page: Page,
  storyId: string,
): Promise<VisualCaptureClip | null> {
  return page.evaluate((id: string) => {
    const preview = (
      window as unknown as {
        __STORYBOOK_PREVIEW__?: {
          storyRenders?: { id: string; story?: { parameters?: Record<string, unknown> } }[]
        }
      }
    ).__STORYBOOK_PREVIEW__
    const render = preview?.storyRenders?.find((r) => r.id === id)
    const clip = render?.story?.parameters?.visualCaptureClip
    return (clip ?? null) as VisualCaptureClip | null
  }, storyId)
}

// What a clip part and a forced state both name: one element, by a CSS `selector`, or by ARIA `role`
// optionally narrowed by `name`, with `nth` breaking a tie when either matches more than one.
export interface ElementTarget {
  selector?: string
  role?: string
  name?: string
  nth?: number
}

// The one locator both `locateClipPart` below and `applyForceState` further down resolve a target
// through (T693: factored out of the two places that each built it inline, so "which element does
// this name" has one definition — and so `tests/visual/state-coverage-runtime.spec.ts`, which
// records the answer for every forced story, asks the very same question the capture does). Scoped
// to `root`; `nth` narrows it. Never throws and never counts: a caller decides what a count other
// than one means.
export function locateTarget(root: Locator, target: ElementTarget): Locator {
  const role = target.role as Parameters<typeof root.getByRole>[0]
  const located = target.selector
    ? root.locator(target.selector)
    : root.getByRole(role, target.name !== undefined ? { name: target.name } : undefined)
  return typeof target.nth === 'number' ? located.nth(target.nth) : located
}

// One clip part's own box, located a selector or a role(+name), scoped to `root`, with `nth`
// breaking a tie. Throws (never returns a shrunken or empty clip) when a part matches zero or
// more-than-one element with no `nth` to disambiguate.
export async function locateClipPart(root: Locator, storyId: string, part: VisualCaptureClipPart) {
  const scoped = locateTarget(root, part)
  const count = await scoped.count()
  if (count !== 1) {
    throw new Error(
      `visualCaptureClip: part ${JSON.stringify(part)} of story "${storyId}" matched ${count} ` +
        'element(s) — expected exactly 1 (add "nth" to disambiguate a part that matches more than one).',
    )
  }
  return scoped
}

// One clip part's own edges — already scroll-adjusted, in page coordinates — plain data with no DOM
// type of its own, so it crosses the `Locator.evaluate` boundary (browser -> Node) without loss and
// the pure function below that consumes it needs no browser to run.
export interface EdgeRect {
  left: number
  top: number
  right: number
  bottom: number
}

// Picks one clip part's own source rect from its element's bounding box and its full list of
// client rects (`getClientRects()`) — both read once, in the browser, by `resolveCaptureClip`
// below, and handed to this function as plain data, so this function itself never touches the DOM
// and is provably unit-testable with synthetic rects alone (`story-render.test.mjs`).
// `fragment` undefined — every clip part before `fragment` existed, and every one that does not
// name it today — returns `boundingRect` unchanged: the exact behaviour this function replaces
// inline. `fragment: 'first'` returns `clientRects[0]` instead, falling back to `boundingRect` only
// if the element reports no client rects at all (defensive; not observed on a real, laid-out
// element — an element with zero boxes has nothing to clip to either way). Any other value throws:
// a known key's own unexpected value is "unknown keys, and so on" applied to that key rather than
// to the object as a whole, and a silently-ignored typo (`'First'`, `'firsy'`) would otherwise ship
// the un-narrowed bounding box with nothing in this pipeline ever saying so.
export function resolveClipPartRect(
  fragment: VisualCaptureClipPart['fragment'],
  boundingRect: EdgeRect,
  clientRects: EdgeRect[],
): EdgeRect {
  if (fragment === undefined) return boundingRect
  if (fragment !== 'first') {
    throw new Error(
      `visualCaptureClip: part carries an unrecognised "fragment" value ${JSON.stringify(fragment)} — only "first" is defined.`,
    )
  }
  return clientRects[0] ?? boundingRect
}

// Resolves a `pad` step name to its px value from the page's own generated `--ds-space-*` custom
// property, never a literal duplicated from `space.json`.
export async function resolvePadPx(page: Page, step: string): Promise<number> {
  return page.evaluate((s: string) => {
    const raw = getComputedStyle(document.documentElement)
      .getPropertyValue(`--ds-space-${s}`)
      .trim()
    if (!raw)
      throw new Error(
        `visualCaptureClip: unknown spacing token step "${s}" (--ds-space-${s} is unset).`,
      )
    const value = Number.parseFloat(raw)
    if (Number.isNaN(value)) {
      throw new Error(
        `visualCaptureClip: could not parse "--ds-space-${s}" value "${raw}" as a number.`,
      )
    }
    return raw.trim().endsWith('rem') ? value * 16 : value
  }, step)
}

// T675 H1 (reviewer finding, PR #105): whether a clip part is actually rendered right now — the
// gate that decides whether its own rect is allowed to enter the union below at all. A `[role=
// "tooltip"]` surface (`Tooltip`'s own shape, `packages/design-system/src/primitives/Tooltip/
// index.tsx`: `<span role="tooltip" hidden={!isOpen}>`) is always present in the DOM, open or not
// — `locateClipPart`'s CSS-selector path matches it either way, unlike a role-based `getByRole`
// locator, which Playwright already excludes from an unrendered element. At rest, `hidden` (the UA
// stylesheet's `display: none`) leaves the element with no box at all, and `getBoundingClientRect()`
// on an element with no box reports (0, 0, 0, 0) — the page origin, not the element's own layout
// position, because it has none. Unioning that rect in unconditionally is what the T675 sweep's
// `dimension-mismatch` pass caught: the clip's own top-left corner silently dragged to (0, 0) the
// moment ANY part happened to be unrendered, 7 of the sweep's 8 flagged pairs.
//
// A part is "rendered" here when it has both a box (`checkVisibility` — `display: none` **and**
// `visibility: hidden` both report no box this way, `visibilityProperty: true` is what adds the
// latter to the check) and non-zero area (defensive: not observed from `checkVisibility` alone, but
// a zero-area box is exactly as useless to clip to as no box at all, and it costs nothing here to
// treat it the same way).
//
// What this deliberately does NOT do: silently expand or degrade a clip when a *different* number
// of its own parts are rendered between two renders being compared — a closed `Tooltip`'s clip
// (button alone) is legitimately smaller than an open one's (button + surface); that size
// difference is the state's own signal, not this function reaching for a workaround. A clip whose
// parts are ALL unrendered in one render has no rect to return at all — not the full page, not a
// single point — so `resolveCaptureClip` throws below rather than guess; no clip in the tree hits
// this today (every affected story keeps at least one part, usually the trigger, rendered at rest).
async function isClipPartRendered(located: Locator): Promise<boolean> {
  return located.evaluate((el) => {
    const hasCheckVisibility = typeof (el as HTMLElement).checkVisibility === 'function'
    const visible = hasCheckVisibility
      ? (el as HTMLElement).checkVisibility({ visibilityProperty: true })
      : true
    if (!visible) return false
    const box = el.getBoundingClientRect()
    return box.width > 0 && box.height > 0
  })
}

// The clip rect `expect(page).toHaveScreenshot` (or, in the sweep, a raw `page.screenshot({clip})`)
// takes: the union of every RENDERED part's own box (page coordinates, `isClipPartRendered` above),
// inflated by `padPx` on every side, clamped to the page's own scrollable extent.
export async function resolveCaptureClip(
  page: Page,
  root: Locator,
  storyId: string,
  clip: VisualCaptureClip,
): Promise<{ x: number; y: number; width: number; height: number }> {
  if (clip.parts.length === 0) {
    throw new Error(`visualCaptureClip: story "${storyId}" names no parts.`)
  }

  const padPx = await resolvePadPx(page, clip.pad ?? '2')

  let union: { left: number; top: number; right: number; bottom: number } | null = null
  for (const part of clip.parts) {
    const located = await locateClipPart(root, storyId, part)
    if (!(await isClipPartRendered(located))) continue
    const { boundingRect, clientRects } = await located.evaluate((el) => {
      const toEdges = (r: DOMRect) => ({
        left: r.left + window.scrollX,
        top: r.top + window.scrollY,
        right: r.right + window.scrollX,
        bottom: r.bottom + window.scrollY,
      })
      return {
        boundingRect: toEdges(el.getBoundingClientRect()),
        clientRects: Array.from(el.getClientRects()).map(toEdges),
      }
    })
    const box = resolveClipPartRect(part.fragment, boundingRect, clientRects)
    union = union
      ? {
          left: Math.min(union.left, box.left),
          top: Math.min(union.top, box.top),
          right: Math.max(union.right, box.right),
          bottom: Math.max(union.bottom, box.bottom),
        }
      : box
  }
  if (!union) {
    throw new Error(
      `visualCaptureClip: story "${storyId}" — every named clip part is unrendered in this ` +
        'render (hidden, display:none, visibility:hidden, or zero-area) — there is no rect to clip to.',
    )
  }

  const pageExtent = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
  }))

  const left = Math.max(0, union.left - padPx)
  const top = Math.max(0, union.top - padPx)
  const right = Math.min(pageExtent.width, union.right + padPx)
  const bottom = Math.min(pageExtent.height, union.bottom + padPx)

  return { x: left, y: top, width: right - left, height: bottom - top }
}

// Navigates to one story at one theme, sets the viewport, and waits until Storybook itself reports
// the story's render `phase` as settled (`completed`/`finished`/`errored` — reached whether or not
// the story carries a `play()`) and until web fonts have finished loading — the exact sequence
// `stories.spec.ts` always ran inline before this factoring, unchanged. Returns the story's own
// `#storybook-root` locator, already waited for visibility.
export async function gotoAndWaitForStorySettled(
  page: Page,
  id: string,
  theme: Theme,
  width: number,
  height: number,
  { autoplay = true }: { autoplay?: boolean } = {},
): Promise<Locator> {
  await page.setViewportSize({ width, height })
  // `autoplay: false` appends `&embed=true` — a real Storybook preview render option (confirmed by
  // reading the installed storybook@10.5.9's own preview runtime: `shouldAutoplay = ({ search }) =>
  // !shouldEmbed({ search })`, `shouldEmbed = ({ search }) => new URLSearchParams(search).get
  // ('embed') === 'true'`), never a hand-rolled convention. Optional and defaulting to the existing
  // behaviour (`stories.spec.ts` never passes it) — a genuinely unplayed render is what
  // `tests/visual/state-signal-sweep.spec.ts`'s own self-paired rest needs for a state story whose
  // `play()` does something a reset cannot reliably reverse (see that file's own header comment for
  // why: a JS-driven reveal keyed to a reference-counted pointer region, `Tooltip`'s own shape,
  // cannot be undone by a bounded number of synthetic mouse moves).
  const embed = autoplay ? '' : '&embed=true'
  await page.goto(`/iframe.html?id=${id}&viewMode=story${embed}&globals=theme:${theme}`)
  const root = page.locator('#storybook-root')
  await root.waitFor({ state: 'visible' })
  await page.waitForFunction(
    (storyId: string) => {
      const preview = (
        window as unknown as {
          __STORYBOOK_PREVIEW__?: { storyRenders?: { id: string; phase?: string }[] }
        }
      ).__STORYBOOK_PREVIEW__
      const render = preview?.storyRenders?.find((r) => r.id === storyId)
      return !!render && ['completed', 'finished', 'errored'].includes(render.phase ?? '')
    },
    id,
    { timeout: 5_000 },
  )
  await page.evaluate(() => document.fonts.ready)
  return root
}

// Drives the real CSS pseudo-class a `visualForceState` names, in this real browser, on the
// already-settled `root` — the exact block `stories.spec.ts` used to run inline. Returns whether
// the caller must release a held mouse button after capturing (`active` holds it down on purpose).
export async function applyForceState(
  page: Page,
  root: Locator,
  forceState: VisualForceState,
  { width, height, fullPage }: { width: number; height: number; fullPage: boolean },
): Promise<{ releaseMouseAfterCapture: boolean }> {
  await page.addStyleTag({
    content: '*, *::before, *::after { transition: none !important; animation: none !important; }',
  })
  const target = locateTarget(root, forceState)
  // T693: a forced target must be exactly one element, as a clip part must (`locateClipPart`). Zero
  // used to surface as a 30-second actionability timeout from `hover()`; two, as Playwright's strict
  // mode refusing the action — and `focus-visible` goes through `evaluate`, which refuses the same
  // way. Saying it here names the story and the target, and keeps "what the force selects" one
  // answer, the one the runtime pass records.
  const count = await target.count()
  if (count !== 1) {
    const storyId = new URL(page.url()).searchParams.get('id') ?? '(unknown story)'
    throw new Error(
      `visualForceState: target ${JSON.stringify(forceState)} of story "${storyId}" matched ${count} ` +
        'element(s) — expected exactly 1 (add "nth" to disambiguate a target that matches more than one).',
    )
  }

  let releaseMouseAfterCapture = false

  if (!fullPage && (forceState.state === 'hover' || forceState.state === 'active')) {
    const contentHeight = await root.evaluate((el) => el.scrollHeight)
    if (contentHeight > height) {
      await page.setViewportSize({ width, height: contentHeight })
    }
  }

  if (forceState.state === 'hover') {
    await target.hover()
  } else if (forceState.state === 'active') {
    await target.hover()
    await page.mouse.down()
    releaseMouseAfterCapture = true
  } else if (forceState.state === 'focus-visible') {
    await target.evaluate((el: HTMLElement) => el.focus())
  }

  return { releaseMouseAfterCapture }
}
