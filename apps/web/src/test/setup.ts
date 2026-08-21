import '@testing-library/jest-dom/vitest'

// jsdom has no layout engine, so `window.matchMedia` (used by `design-system`'s `useBreakpoint`,
// pulled in transitively through `ProfileSummary` and `SignInScreen`) does not exist by default.
// Every test runs "mobile-first": matches nothing unless a test overrides it, which is also this
// package's own default before the first effect runs. Copied from
// packages/design-system/src/test/setup.ts, which this apps/web test runner mirrors.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}
