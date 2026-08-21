import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Unit tests exercise behaviour and accessibility with Testing Library, never pixels — pixels are
// the visual-reviewer's job over the Storybook stories (design-system skill, checklist points 7
// and 8). jsdom is enough for that: no browser, no screenshot, no token resolution needed.
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
