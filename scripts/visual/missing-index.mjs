// What `run.mjs` does when the built Storybook index is absent, as a pure function so
// `state-signal-model.test.mjs` can assert it. A module of its own with no imports, because
// `run.mjs` loads it for every run, while `state-signal-model.mjs` needs `typescript` and
// `storybook/internal/csf` at load time and is loaded only for `--state-signal-sweep`.
//
// The two modes differ. The ordinary run has nothing to test before any story exists.
// The sweep's work list comes from the built index, so with no index it has measured nothing:
// a gate failure, not a pass.

export const BUILD_STORYBOOK_COMMAND = 'pnpm --filter design-system build-storybook'

const INDEX_DISPLAY_PATH = 'packages/design-system/storybook-static/index.json'

// `{ proceed: true }` when the index exists; otherwise `{ proceed: false, exitCode, message }`.
export function decideMissingIndex({ indexExists, sweepMode }) {
  if (indexExists) return { proceed: true }
  if (sweepMode) {
    return {
      proceed: false,
      exitCode: 1,
      message:
        `state-signal-sweep: gate failed — no Storybook build found at ${INDEX_DISPLAY_PATH}, so ` +
        `there is nothing to sweep. Run \`${BUILD_STORYBOOK_COMMAND}\` first.`,
    }
  }
  return {
    proceed: false,
    exitCode: 0,
    message:
      `no Storybook build found at ${INDEX_DISPLAY_PATH} — nothing to test. Run ` +
      `\`${BUILD_STORYBOOK_COMMAND}\` first if stories already exist.`,
  }
}
