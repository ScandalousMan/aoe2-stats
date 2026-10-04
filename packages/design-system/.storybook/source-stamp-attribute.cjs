// The name of the attribute the source stamp writes — the ONE definition (T693, feature 005).
//
// A `.cjs`, deliberately: the transform that writes the attribute (`./source-stamp.mjs`, loaded by
// Vite through `./main.ts`) and the Playwright specs that read it (`tests/visual/state-coverage-
// runtime*.ts`) both need the name, and a Playwright spec is transpiled to CommonJS. `source-stamp.mjs`
// uses `import.meta`, which cannot be loaded from there — it crashed CI on Node 20.20 with `exports is
// not defined in ES module scope`, and fails the same way on Node 20.13 and 24. A `.cjs` is
// unambiguously CommonJS by extension, the precedent `scripts/visual/a11y-scan.cjs` set. `.mjs`
// importers read it through Node's named-export detection of `exports.X = ...`.
'use strict'

exports.STAMP_ATTRIBUTE = 'data-ds-src'
