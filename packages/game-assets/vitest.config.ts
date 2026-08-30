import { defineConfig } from 'vitest/config'

// This package holds no component and no React — just the pack directories and the resolver
// T409 adds. `passWithNoTests` keeps `pnpm -r test` green between this task (the scaffold) and
// T408 (the resolver's tests): a package with a `test` script and zero test files is the normal
// state of a workspace member mid-build, not a failure.
export default defineConfig({
  test: {
    include: ['src/**/*.test.ts'],
    passWithNoTests: true,
  },
})
