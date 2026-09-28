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

export interface VisualCaptureClipPart {
  selector?: string
  role?: string
  name?: string
  nth?: number
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

// One clip part's own box, located a selector or a role(+name), scoped to `root`, with `nth`
// breaking a tie. Throws (never returns a shrunken or empty clip) when a part matches zero or
// more-than-one element with no `nth` to disambiguate.
export async function locateClipPart(root: Locator, storyId: string, part: VisualCaptureClipPart) {
  const role = part.role as Parameters<typeof root.getByRole>[0]
  const located = part.selector
    ? root.locator(part.selector)
    : root.getByRole(role, part.name !== undefined ? { name: part.name } : undefined)
  const scoped = typeof part.nth === 'number' ? located.nth(part.nth) : located
  const count = await scoped.count()
  if (count !== 1) {
    throw new Error(
      `visualCaptureClip: part ${JSON.stringify(part)} of story "${storyId}" matched ${count} ` +
        'element(s) — expected exactly 1 (add "nth" to disambiguate a part that matches more than one).',
    )
  }
  return scoped
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

// The clip rect `expect(page).toHaveScreenshot` (or, in the sweep, a raw `page.screenshot({clip})`)
// takes: the union of every part's own box (page coordinates), inflated by `padPx` on every side,
// clamped to the page's own scrollable extent.
export async function resolveCaptureClip(
  page: Page,
  root: Locator,
  storyId: string,
  clip: VisualCaptureClip,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const padPx = await resolvePadPx(page, clip.pad ?? '2')

  let union: { left: number; top: number; right: number; bottom: number } | null = null
  for (const part of clip.parts) {
    const located = await locateClipPart(root, storyId, part)
    const box = await located.evaluate((el) => {
      const rect = el.getBoundingClientRect()
      return {
        left: rect.left + window.scrollX,
        top: rect.top + window.scrollY,
        right: rect.right + window.scrollX,
        bottom: rect.bottom + window.scrollY,
      }
    })
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
    throw new Error(`visualCaptureClip: story "${storyId}" names no parts.`)
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
): Promise<Locator> {
  await page.setViewportSize({ width, height })
  await page.goto(`/iframe.html?id=${id}&viewMode=story&globals=theme:${theme}`)
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
  const target = (() => {
    const role = forceState.role as Parameters<typeof root.getByRole>[0]
    const located = forceState.selector
      ? root.locator(forceState.selector)
      : root.getByRole(role, forceState.name !== undefined ? { name: forceState.name } : undefined)
    return typeof forceState.nth === 'number' ? located.nth(forceState.nth) : located
  })()

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
