import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Mirrors packages/design-system/vitest.config.ts: unit tests exercise behaviour and
// accessibility with Testing Library, never pixels — pixels are the visual-reviewer's job over
// Storybook stories (design-system skill, checklist points 7 and 8). jsdom is enough for that: no
// browser, no screenshot, no token resolution needed. This config deliberately omits the
// TanStack Router vite plugin and the Tailwind plugin that `vite.config.ts` needs for the real
// app build — tests import feature modules and containers directly, never a generated route tree
// or compiled CSS.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // Testing Library's auto-cleanup between tests hooks the test framework's global `afterEach`;
    // without `globals: true` it never finds one and every test after the first inherits the
    // previous test's DOM.
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
