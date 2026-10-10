// Declaration for the one export of `./story-index.mjs` a `.ts` importer reads today:
// `tests/visual/state-signal-sweep.spec.ts` takes the full-page tag from it instead of writing the
// literal. TypeScript pairs a `.d.mts` with the `.mjs` module of the same name automatically; the
// other exports are plain JavaScript for the Node scripts and are declared when a `.ts` file needs one.
export declare const FULL_PAGE_TAG: string
