// A browserless stand-in for the page a story settles in (T712), for the plants of the ORDER the
// harness drives a page in: which call comes before which, and what a handler the force triggers can
// change by then. It is not a browser and proves nothing about what Chromium does; it proves what the
// harness asks of the page, and when. `story-render.ts`'s readers run against it unchanged, because
// `evaluate` runs their function in Node against a `window` the stub owns.
//
// What it simulates, and no more:
//   - `window.__STORYBOOK_PREVIEW__.storyRenders` for one story: its `parameters` (a handler may write
//     `visualCaptureClip` into them, as a real one can) and no `play()`.
//   - the tracked-primitive registry the probe asserts is present.
//   - `inspect`'s three questions, answered from what the test says the page holds NOW, so a handler
//     that changes the answer when the force is applied is visible in what the harness reads.
//   - a navigation (`navigate()`): the document is replaced, so a property set on the old window is gone,
//     as it is in a browser, and `__STORYBOOK_PREVIEW__` with it. A page that is not a story page
//     (the address has no `iframe.html`) holds no `#storybook-root`, so a read through the story root
//     rejects, as a locator on an element that is not in the document does when its wait runs out.
//   - the order of every call that matters, in `calls`.
import type { Locator, Page } from '@playwright/test'

export interface StubState {
  // What `inspect` answers for each mode, read when the harness asks.
  mounts: () => unknown[]
  files: () => string[]
  element: () => unknown
  // Called when the force reaches the control: `hover()` for a hover or an active force.
  onHover?: (stub: StubStoryPage) => void
  // Called when the mouse button goes down on the control.
  onMouseDown?: (stub: StubStoryPage) => void
  // Number of elements the force's locator finds.
  matches?: number
  // Whether the forced element itself is disabled now (`:disabled` or `aria-disabled="true"`). A
  // boolean is a native `:disabled`; the object says which of the two the page reports (T745).
  disabled?: () => boolean | { native: boolean; aria: boolean }
}

export interface StubStoryPage {
  page: Page
  root: Locator
  calls: string[]
  // The story's parameters, written by a handler through `stub.parameters`.
  parameters: Record<string, unknown>
  // Replaces the document, as a navigation does.
  navigate: (url: string) => void
  // What the page's current document holds: gone after `navigate`.
  windowHolds: (key: string) => boolean
}

type FakeWindow = Record<string, unknown>

// `id` is the story the preview reports; `url` where the page starts.
export function stubStoryPage(
  id: string,
  state: StubState,
  url = 'http://stub/iframe.html',
): StubStoryPage {
  const calls: string[] = []
  const parameters: Record<string, unknown> = {}
  // Reading the clip is the event the order plants look for, so the parameters object reports it.
  const observed = new Proxy(parameters, {
    get(target, key) {
      if (key === 'visualCaptureClip') calls.push('read clip')
      return Reflect.get(target, key)
    },
  })
  const freshWindow = (): FakeWindow => ({
    __DS_TRACKED_PRIMITIVES__: {},
    __STORYBOOK_PREVIEW__: { storyRenders: [{ id, story: { parameters: observed } }] },
  })
  let currentWindow = freshWindow()
  let currentUrl = url
  let rootInDocument = true

  // Runs a page function in Node with `window` and the two storages bound to the current document's.
  const storageNamed = (name: string) => ({ clear: () => void calls.push(`clear ${name}`) })
  const local = storageNamed('localStorage')
  const session = storageNamed('sessionStorage')
  const run = async (fn: unknown, arg: unknown) => {
    const g = globalThis as Record<string, unknown>
    const saved = ['window', 'localStorage', 'sessionStorage'].map((key) => [key, g[key]] as const)
    g.window = currentWindow
    g.localStorage = local
    g.sessionStorage = session
    try {
      return await (fn as (a: unknown) => unknown)(arg)
    } finally {
      for (const [key, value] of saved) g[key] = value
    }
  }

  const targetOf = (): Locator =>
    ({
      count: async () => state.matches ?? 1,
      nth() {
        return this
      },
      hover: async () => {
        calls.push('hover')
        state.onHover?.(stub)
      },
      evaluate: async (_fn: unknown, options: { mode?: string } | undefined) => {
        if (options?.mode === 'element') return state.element()
        // The disabled question (`el.matches(':disabled')`, `aria-disabled`): answered by the test.
        const answer = state.disabled?.() ?? false
        return typeof answer === 'boolean' ? { native: answer, aria: false } : answer
      },
    }) as unknown as Locator

  const root = {
    locator: () => targetOf(),
    getByRole: () => targetOf(),
    screenshot: async () => {
      calls.push('screenshot')
      return Buffer.alloc(0)
    },
    evaluate: async (_fn: unknown, options: { mode?: string }) => {
      if (!rootInDocument) {
        throw new Error('locator.evaluate: Timeout exceeded waiting for locator("#storybook-root")')
      }
      if (options?.mode === 'mounts') {
        calls.push('read mounts')
        return state.mounts()
      }
      if (options?.mode === 'files') {
        calls.push('read files')
        return state.files()
      }
      return 0
    },
  } as unknown as Locator

  const page = {
    url: () => currentUrl,
    context: () => ({ clearCookies: async () => void calls.push('clear cookies') }),
    evaluate: async (fn: unknown, arg: unknown) => {
      return run(fn, arg)
    },
    addStyleTag: async () => {},
    setViewportSize: async () => {},
    goto: async (target: string) => {
      calls.push(`goto ${target}`)
      stub.navigate(target)
    },
    screenshot: async () => {
      calls.push('screenshot')
      return Buffer.alloc(0)
    },
    mouse: {
      down: async () => {
        calls.push('mouse.down')
        state.onMouseDown?.(stub)
      },
      up: async () => {
        // Where the button comes up is the point: over the story it is a click.
        calls.push(`mouse.up on ${currentUrl === 'about:blank' ? 'about:blank' : 'the story'}`)
      },
    },
  } as unknown as Page

  const stub: StubStoryPage = {
    page,
    root,
    calls,
    parameters,
    navigate: (to) => {
      currentUrl = to
      rootInDocument = to.includes('iframe.html')
      currentWindow = to.includes('iframe.html') ? freshWindow() : {}
    },
    windowHolds: (key) => key in currentWindow,
  }
  return stub
}
