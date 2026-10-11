// When two tracked-primitive instances are the same one (T712).
//
// An instance is what `tests/visual/state-coverage-runtime.ts` records of a tracked primitive the story
// mounted: `{ component, variant, size, disabledAt }`. Two readers join instances across renders and
// must agree on what "the same" means: the runtime pass, across the light and the dark theme
// (`combineThemeRecords`), and `scripts/checks/state-coverage.mjs`, across the captured widths
// (`stableMounts`). This is the one definition they share; a field added to an instance is added here
// once. `variant` and `size` are `null` for an axis a primitive lacks, and a record from an older pass
// may omit them, so absent and `null` are the same; `disabledAt` is a set of stamps, so its order is not.
// The input is never reordered in place.
//
// No import and no module-URL meta property: a spec Playwright transpiles to CommonJS imports this
// file (`story-index.mjs` is the same shape, and `source-stamp.test.mjs` pins the property).
export function instanceKey(instance) {
  return JSON.stringify([
    instance.component,
    instance.variant ?? null,
    instance.size ?? null,
    [...(instance.disabledAt ?? [])].sort(),
  ])
}
