// T675 (slice 2/N): unit tests for state-signal-model.mjs's own pure parts — self-pairing and
// bucket classification never touch a filesystem or a browser, so both are provable against small,
// hand-written fixtures rather than the real tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { createRequire } from 'node:module'
import {
  extractFileStoryStates,
  planSelfRest,
  classifyBucket,
  extractVisualCaptureClip,
  decideSweepGate,
  buildStoryFileWork,
  buildStateSignalWork,
  groupIndexByFile,
  reconcileFile,
  findUnindexedStoryFiles,
  listStoryFilesOnDisk,
  parseSweepIndex,
  STORY_WALK_ROOTS,
  STORY_FILE_EXTENSIONS,
  dsDir,
  rootDir,
} from './state-signal-model.mjs'
import { decideMissingIndex, BUILD_STORYBOOK_COMMAND } from './missing-index.mjs'

// A minimal CSF file exercising every shape `planSelfRest` decides between:
//   - `Primary`: a plain resting story (not a state story at all).
//   - `Hover`: a `visualForceState` story — the `'forced'` mode, the common case (109 of 113 real
//     state stories).
//   - `TriggerFocusVisibleByRef`: a `visualForceState` story whose own `visualCaptureClip` is a
//     top-level const referenced by identifier, not written inline — proves `extractVisualCaptureClip`
//     still resolves it the same way slice 1 fixed.
//   - `RoleAsConstClip`: a clip part's own role annotated `as const` — the second real
//     `extractVisualCaptureClip` defect slice 1 fixed, still exercised here.
//   - `KeyboardEndsFocused`: no `visualForceState`, but its own play() ends with a real
//     `toHaveFocus()` assertion on a `getByRole` target — the `'play-focus-blur'` mode
//     (`Dialog.stories.tsx`'s own `KeyboardFocusOrderAndTrap` shape).
//   - `MysteryFocus`: no `visualForceState`, and its own play() calls `.focus()` on an element this
//     static pass cannot resolve to a role or selector at all — the one static "not measurable" case
//     `planSelfRest` still reports, unexercised by any real story in the tree today.
const FIXTURE_SOURCE = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { Widget } from './index'

const TRIGGER_CLIP = { parts: [{ role: 'button', name: 'Manage' }], pad: '2' }
const AS_CONST_CLIP = { parts: [{ role: 'button', name: 'Manage' }], pad: '2' } as const

const meta: Meta<typeof Widget> = {
  id: 'primitives-widget',
  title: 'Primitives/Widget',
  component: Widget,
  args: { label: 'Continue' },
}

export default meta
type Story = StoryObj<typeof Widget>

export const Primary: Story = {
  args: { variant: 'primary', size: 'lg' },
}

export const Hover: Story = {
  args: { variant: 'primary', size: 'lg' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const TriggerFocusVisibleByRef: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button' },
    visualCaptureClip: TRIGGER_CLIP,
  },
}

export const RoleAsConstClip: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'hover', role: 'link' },
    visualCaptureClip: { parts: [{ role: 'link' as const }], pad: '2' },
  },
}

export const TriggerHoverByRefAsConst: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'hover', role: 'button' },
    visualCaptureClip: AS_CONST_CLIP,
  },
}

export const InlineAsConstClip: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'active', role: 'button' },
    visualCaptureClip: { parts: [{ role: 'button', name: 'Manage' }], pad: '2' } as const,
  },
}

export const FragmentFirstClip: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'hover', role: 'link' },
    visualCaptureClip: { parts: [{ role: 'link', fragment: 'first' as const }], pad: '2' },
  },
}

export const KeyboardEndsFocused: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const primary = canvas.getByRole('button', { name: 'Turn it off' })
    await expect(primary).toHaveFocus()
  },
}

export const MysteryFocus: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  play: async ({ canvasElement }) => {
    const el = canvasElement.querySelector('.mystery')
    el.focus()
  },
}
`

function fixtureStories() {
  const result = extractFileStoryStates('fixture.stories.tsx', FIXTURE_SOURCE)
  const byName = new Map(result.stories.map((s) => [s.exportName, s]))
  return { result, byName }
}

test('extractFileStoryStates computes ids the same way the real Storybook build does', () => {
  const { byName } = fixtureStories()
  assert.equal(byName.get('Primary').id, 'primitives-widget--primary')
  assert.equal(byName.get('KeyboardEndsFocused').id, 'primitives-widget--keyboard-ends-focused')
})

test('extractFileStoryStates marks a forced story and a play-focus story isStateStory, a plain one not', () => {
  const { byName } = fixtureStories()
  assert.equal(byName.get('Hover').isStateStory, true)
  assert.equal(byName.get('KeyboardEndsFocused').isStateStory, true)
  assert.equal(byName.get('Primary').isStateStory, false)
})

test('extractVisualCaptureClip resolves a clip referenced by identifier, not only one written inline', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('TriggerFocusVisibleByRef').clip, {
    parts: [
      { selector: undefined, role: 'button', name: 'Manage', nth: undefined, fragment: undefined },
    ],
    pad: '2',
  })
})

test('extractVisualCaptureClip resolves a part role annotated "as const", not only a bare literal', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('RoleAsConstClip').clip, {
    parts: [
      { selector: undefined, role: 'link', name: undefined, nth: undefined, fragment: undefined },
    ],
    pad: '2',
  })
})

// T675 slice 4b: `buildTopLevelConstNodeMap` used to store the raw `AsExpression` for a top-level
// `const X = {...} as const` — the shape most `visualCaptureClip` constants in the real tree use —
// so `extractVisualCaptureClip`'s own `ts.isObjectLiteralExpression(clip)` check failed and treated
// a real, present clip as absent (`hasClip: false`, and `.clip: null`). Fixed by `unwrapExpression`
// (state-coverage.mjs), shared by both the const-map path and the inline path below.
test('extractVisualCaptureClip resolves a clip referenced by identifier whose own declaration is annotated "as const"', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('TriggerHoverByRefAsConst').clip, {
    parts: [
      { selector: undefined, role: 'button', name: 'Manage', nth: undefined, fragment: undefined },
    ],
    pad: '2',
  })
})

test('extractVisualCaptureClip resolves a clip written inline and annotated "as const", not only one referenced by identifier', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('InlineAsConstClip').clip, {
    parts: [
      { selector: undefined, role: 'button', name: 'Manage', nth: undefined, fragment: undefined },
    ],
    pad: '2',
  })
})

// T675 slice 4c: `fragment` extracted the same way every other clip-part field already is.
test('extractVisualCaptureClip resolves a part\'s own "fragment" option, not only role/name/selector/nth', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('FragmentFirstClip').clip, {
    parts: [
      { selector: undefined, role: 'link', name: undefined, nth: undefined, fragment: 'first' },
    ],
    pad: '2',
  })
})

test('planSelfRest: a visualForceState story self-pairs in "forced" mode', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(planSelfRest(byName.get('Hover')), { measurable: true, mode: 'forced' })
})

test('planSelfRest: a play()-ending-focused story self-pairs in "play-focus-blur" mode', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(planSelfRest(byName.get('KeyboardEndsFocused')), {
    measurable: true,
    mode: 'play-focus-blur',
  })
})

test('planSelfRest: a play()-story whose focus target cannot be resolved stays not measurable, with its reason', () => {
  const { byName } = fixtureStories()
  const story = byName.get('MysteryFocus')
  // Confirms the fixture actually hits the "unresolved" branch — a false pass here (this story
  // silently resolving to a real role) would make the assertion below prove nothing.
  assert.equal(story.playFocus?.role, 'unresolved')
  const plan = planSelfRest(story)
  assert.equal(plan.measurable, false)
  assert.equal(plan.reason, 'play-focus-target-unresolved')
  assert.match(plan.detail, /MysteryFocus/)
})

test('planSelfRest: a plain resting story is not a state story at all', () => {
  const { byName } = fixtureStories()
  const plan = planSelfRest(byName.get('Primary'))
  assert.equal(plan.measurable, false)
  assert.equal(plan.reason, 'not-a-state-story')
})

test('classifyBucket: zero surviving pixels on every unit, unclipped — no clip can help', () => {
  const units = [
    { theme: 'light', width: 375, diffPixels: 0, totalPixels: 100, ratio: 0 },
    { theme: 'dark', width: 1280, diffPixels: 0, totalPixels: 100, ratio: 0 },
  ]
  assert.deepEqual(classifyBucket({ hasClip: false, unitResults: units }), {
    bucket: 'zero',
    minRatio: 0,
  })
})

test("classifyBucket: zero surviving pixels despite an existing clip — Dialog Hover's own shape", () => {
  const units = [{ theme: 'light', width: 375, diffPixels: 0, totalPixels: 100, ratio: 0 }]
  assert.deepEqual(classifyBucket({ hasClip: true, unitResults: units }), {
    bucket: 'zero-despite-clip',
    minRatio: 0,
  })
})

test('classifyBucket: a real signal at or under 1% on at least one unit, unclipped — a clip fixes it', () => {
  const units = [
    { theme: 'light', width: 375, diffPixels: 5, totalPixels: 1000, ratio: 0.005 },
    { theme: 'dark', width: 1280, diffPixels: 400, totalPixels: 1000, ratio: 0.4 },
  ]
  assert.deepEqual(classifyBucket({ hasClip: false, unitResults: units }), {
    bucket: 'clip-fixes',
    minRatio: 0.005,
  })
})

test('classifyBucket: already clipped and still at or under 1% — a clip that does not defend', () => {
  const units = [{ theme: 'light', width: 375, diffPixels: 5, totalPixels: 1000, ratio: 0.005 }]
  assert.deepEqual(classifyBucket({ hasClip: true, unitResults: units }), {
    bucket: 'clipped-still-under-threshold',
    minRatio: 0.005,
  })
})

test('classifyBucket: defended, already clipped, over 1% on every unit', () => {
  const units = [
    { theme: 'light', width: 375, diffPixels: 50, totalPixels: 1000, ratio: 0.05 },
    { theme: 'dark', width: 1280, diffPixels: 30, totalPixels: 1000, ratio: 0.03 },
  ]
  assert.deepEqual(classifyBucket({ hasClip: true, unitResults: units }), {
    bucket: 'defended',
    minRatio: 0.03,
  })
})

test('classifyBucket: defended without ever needing a clip', () => {
  const units = [{ theme: 'light', width: 375, diffPixels: 50, totalPixels: 1000, ratio: 0.05 }]
  assert.deepEqual(classifyBucket({ hasClip: false, unitResults: units }), {
    bucket: 'defended-without-clip',
    minRatio: 0.05,
  })
})

test('classifyBucket: a zero-looking diff whose state frame does not match its own baseline is state-not-reproduced, never zero', () => {
  // The exact shape slice 3's own defect had: `Tooltip` `HoverRevealed`'s own state capture still
  // showed the rest, not the state (the reset had not finished before the "rest" was captured), so
  // the pixel diff between the two reads zero — but the *state* frame this sweep actually captured
  // never matched the story's own committed baseline at all, which is what this override catches.
  const units = [
    {
      theme: 'light',
      width: 1280,
      diffPixels: 0,
      totalPixels: 1000,
      ratio: 0,
      dimensionMismatch: false,
      stateMatchesBaseline: false,
    },
  ]
  const result = classifyBucket({ hasClip: false, unitResults: units })
  assert.equal(result.bucket, 'state-not-reproduced')
})

test('classifyBucket: state-not-reproduced overrides every other question, not only a zero-looking one', () => {
  const units = [
    {
      theme: 'light',
      width: 1280,
      diffPixels: 500,
      totalPixels: 1000,
      ratio: 0.5,
      dimensionMismatch: false,
      stateMatchesBaseline: false,
    },
  ]
  const result = classifyBucket({ hasClip: true, unitResults: units })
  assert.equal(result.bucket, 'state-not-reproduced')
})

test('classifyBucket: a missing baseline (stateMatchesBaseline null) is not a failure — classifies normally', () => {
  const units = [
    {
      theme: 'light',
      width: 1280,
      diffPixels: 0,
      totalPixels: 1000,
      ratio: 0,
      dimensionMismatch: false,
      stateMatchesBaseline: null,
    },
  ]
  const result = classifyBucket({ hasClip: false, unitResults: units })
  assert.equal(result.bucket, 'zero')
})

test('classifyBucket: a dimension mismatch is reported rather than silently ratioed', () => {
  const units = [
    {
      theme: 'light',
      width: 375,
      diffPixels: null,
      totalPixels: null,
      ratio: null,
      dimensionMismatch: true,
    },
  ]
  const result = classifyBucket({ hasClip: false, unitResults: units })
  assert.equal(result.bucket, 'dimension-mismatch')
})

// --- decideSweepGate -----------------------------------------------------------------------------
// T675 slice 4b + remediation (M1, reviewer finding by reading): the sweep's own "no allowlist"
// claim failed open in three ways — a story file with no `meta.id` was only logged and skipped
// (never reaching this function at all), a not-measurable state story never reached it either, and
// an empty or short `classified` list passed vacuously. `decideSweepGate` now takes the whole shape
// `run.mjs`'s own sweep produces — `classified`, `measurableCount`, `notMeasurable`,
// `unkeyableFiles` — and fails on all four, named. Every one of `classifyBucket`'s eight buckets is
// still exercised once here, on a minimal `{ stateId, bucket }` shape (`decideSweepGate` reads only
// `bucket` from a classified entry, never the unit-level detail `classifyBucket` itself already owns
// and this file's own tests above already cover) — `gate(...)` below supplies `measurableCount` as
// `classified.length` for every one of those so only the bucket question is under test, not (c).
function entry(stateId, bucket) {
  return { stateId, bucket }
}

// Matches `classified` 1:1 for `measurableCount` unless a test overrides it — every test below that
// is not itself testing (c) wants the count question answered "yes" automatically, the same way the
// pre-remediation tests implicitly assumed it by never mentioning it at all.
function gate(classified, overrides = {}) {
  return decideSweepGate({
    classified,
    measurableCount: classified.length,
    notMeasurable: [],
    unkeyableFiles: [],
    ...overrides,
  })
}

test('decideSweepGate: defended and defended-without-clip both pass', () => {
  const classified = [entry('a', 'defended'), entry('b', 'defended-without-clip')]
  assert.deepEqual(gate(classified), { pass: true, failures: [] })
})

test('decideSweepGate: dimension-mismatch passes — a size change fails toHaveScreenshot by construction', () => {
  const classified = [entry('a', 'dimension-mismatch')]
  assert.deepEqual(gate(classified), { pass: true, failures: [] })
})

test('decideSweepGate: zero and zero-despite-clip both fail, named', () => {
  const classified = [entry('a', 'zero'), entry('b', 'zero-despite-clip')]
  const result = gate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['a', 'b'],
  )
})

test('decideSweepGate: clip-fixes and clipped-still-under-threshold both fail — a real signal that still does not clear the comparator', () => {
  const classified = [entry('a', 'clip-fixes'), entry('b', 'clipped-still-under-threshold')]
  const result = gate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['a', 'b'],
  )
})

test('decideSweepGate: state-not-reproduced fails — the sweep could not confirm the frame it measured', () => {
  const classified = [entry('a', 'state-not-reproduced')]
  const result = gate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['a'],
  )
})

test('decideSweepGate: one failing story fails the whole gate, alongside any number of passing ones', () => {
  const classified = [
    entry('good-1', 'defended'),
    entry('good-2', 'dimension-mismatch'),
    entry('bad', 'zero'),
    entry('good-3', 'defended-without-clip'),
  ]
  const result = gate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['bad'],
  )
})

// (a) M1: a story file with no literal `meta.id` used to be only logged and skipped by the caller
// (`run.mjs`'s own `buildStateSignalWork`, pre-remediation) — it never reached `decideSweepGate` at
// all, so a whole file's worth of state stories could vanish from the sweep silently. Now
// `unkeyableFiles` (built by `buildStoryFileWork`, see its own test below) is an unconditional,
// named gate failure.
test('decideSweepGate: an unkeyable story file fails the gate, named by file — even with an otherwise-clean classified set', () => {
  const classified = [entry('a', 'defended')]
  const result = gate(classified, {
    unkeyableFiles: [{ file: 'src/primitives/Ghost/Ghost.stories.tsx', detail: 'no meta.id' }],
  })
  assert.equal(result.pass, false)
  const failure = result.failures.find((f) => f.kind === 'unkeyable-file')
  assert.ok(failure, 'expected an unkeyable-file failure')
  assert.equal(failure.file, 'src/primitives/Ghost/Ghost.stories.tsx')
  assert.match(failure.detail, /no meta\.id/)
})

// (b) M1: a not-measurable state story used to never reach this function — only `measurable`'s
// eventual classifications did. Per this finding's own instruction: `planSelfRest`'s one real
// "not measurable" reason for an actual state story, `'play-focus-target-unresolved'`, is not a
// by-design exemption (that function's own comment calls it a real gap this sweep cannot confirm
// past), so there is no allowlist here — every `notMeasurable` entry fails, named with its reason.
test('decideSweepGate: a not-measurable state story fails the gate, named with its reason — even with an otherwise-clean classified set', () => {
  const classified = [entry('a', 'defended')]
  const result = gate(classified, {
    notMeasurable: [
      {
        stateId: 'primitives-widget--mystery-focus',
        file: 'src/primitives/Widget/Widget.stories.tsx',
        reason: 'play-focus-target-unresolved',
        detail: "MysteryFocus's own play() calls .focus() on a target this sweep cannot resolve.",
      },
    ],
  })
  assert.equal(result.pass, false)
  const failure = result.failures.find((f) => f.kind === 'not-measurable')
  assert.ok(failure, 'expected a not-measurable failure')
  assert.equal(failure.stateId, 'primitives-widget--mystery-focus')
  assert.equal(failure.reason, 'play-focus-target-unresolved')
  assert.match(failure.detail, /MysteryFocus/)
})

// (c-empty) M1: `decideSweepGate([])` used to pass vacuously — "nothing measured" and "everything
// measured passed" were indistinguishable. Replaces the old
// "empty input passes vacuously" test outright, per this finding's own instruction.
test('decideSweepGate: an empty classified list fails — nothing measured is not nothing to prove', () => {
  const result = decideSweepGate({
    classified: [],
    measurableCount: 0,
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.equal(result.pass, false)
  assert.ok(
    result.failures.some((f) => f.kind === 'no-classifications'),
    'expected a no-classifications failure',
  )
})

// (c-count-mismatch) M1: a measurable pair that produced no classification (a Playwright test that
// crashed, for instance) used to be invisible — `decideSweepGate` read only `classified`, with no
// way to know how many pairs had been planned in the first place.
test('decideSweepGate: classified shorter than measurableCount fails — a measurable pair produced no classification', () => {
  const classified = [entry('a', 'defended')]
  const result = decideSweepGate({
    classified,
    measurableCount: 2,
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.equal(result.pass, false)
  const failure = result.failures.find((f) => f.kind === 'measurable-count-mismatch')
  assert.ok(failure, 'expected a measurable-count-mismatch failure')
  assert.match(failure.detail, /2 measurable pair\(s\) were planned but 1 were classified/)
})

test('decideSweepGate: classified longer than measurableCount also fails — the count must match exactly', () => {
  const classified = [entry('a', 'defended'), entry('b', 'defended')]
  const result = decideSweepGate({
    classified,
    measurableCount: 1,
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.equal(result.pass, false)
  assert.ok(result.failures.some((f) => f.kind === 'measurable-count-mismatch'))
})

// The contrast: a full, matching, all-defended classification — no unkeyable file, no not-measurable
// story, `classified.length === measurableCount` — passes cleanly.
// T675 remediation (N3): `measurableCount` alone cannot tell a same-length swap apart from a clean
// run — `classified` here has the same length as `measurableIds` but a different member (`c`
// instead of `b`). Before this finding's fix, `decideSweepGate` had no `measurableIds` parameter at
// all, so this case passed cleanly (RED against pre-fix code: `gate.pass` was `true`, and
// `gate.failures` had no `measurable-id-mismatch` entry — confirmed by running this exact test
// against the code before `measurableIds` was added). Fixed by comparing the two lists as sets.
test('decideSweepGate: same-length classified and measurableIds sets that differ by member fail, named', () => {
  const classified = [entry('a', 'defended'), entry('c', 'defended')]
  const result = decideSweepGate({
    classified,
    measurableCount: classified.length,
    measurableIds: ['a', 'b'],
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.equal(result.pass, false)
  const failure = result.failures.find((f) => f.kind === 'measurable-id-mismatch')
  assert.ok(failure, 'expected a measurable-id-mismatch failure')
  assert.match(failure.detail, /missing.*\bb\b/)
  assert.match(failure.detail, /unexpected.*\bc\b/)
})

test('decideSweepGate: measurableIds that exactly match classified ids pass (control for the case above)', () => {
  const classified = [entry('a', 'defended'), entry('b', 'defended')]
  const result = decideSweepGate({
    classified,
    measurableCount: classified.length,
    measurableIds: ['a', 'b'],
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.deepEqual(result, { pass: true, failures: [] })
})

test('decideSweepGate: measurableIds omitted (existing callers) does not perform the set check at all', () => {
  const classified = [entry('a', 'defended')]
  const result = gate(classified)
  assert.deepEqual(result, { pass: true, failures: [] })
})

test('decideSweepGate: a full, matching, all-defended classification passes', () => {
  const classified = [
    entry('a', 'defended'),
    entry('b', 'defended-without-clip'),
    entry('c', 'dimension-mismatch'),
  ]
  const result = decideSweepGate({
    classified,
    measurableCount: classified.length,
    notMeasurable: [],
    unkeyableFiles: [],
  })
  assert.deepEqual(result, { pass: true, failures: [] })
})

// --- buildStoryFileWork ----------------------------------------------------------------------
// T675 remediation (M1, finding (a)): the pure per-file decision `run.mjs`'s own file-scan loop
// needs, extracted so "a story file with no literal meta.id" is provable at the unit level rather
// than only by reading `run.mjs`'s own try/catch.

test('buildStoryFileWork: a file with no literal meta.id is reported as unkeyable, not silently skipped', () => {
  const source = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { Widget } from './index'

const meta: Meta<typeof Widget> = {
  title: 'Primitives/Widget',
  component: Widget,
}

export default meta
type Story = StoryObj<typeof Widget>

export const Hover: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`
  const filePath = path.join(rootDir, 'src/primitives/Widget/Widget.stories.tsx')
  const work = buildStoryFileWork(filePath, source)
  assert.ok(work.unkeyable, 'expected an unkeyable result')
  assert.equal(work.unkeyable.file, 'src/primitives/Widget/Widget.stories.tsx')
  assert.match(work.unkeyable.detail, /no string-literal "id"/)
  assert.equal(work.measurable, undefined)
  assert.equal(work.notMeasurable, undefined)
})

// T675 remediation (N3, the twin of M1(a)): a file with no meta object at all (no top-level const
// with a "component" property — `findMeta` returns `null`) used to make `extractFileStoryStates`
// itself `return null`, and `buildStoryFileWork`'s own `if (result) { ... }` turned that into an
// empty `{ measurable: [], notMeasurable: [] }` — silently, with no `unkeyable` entry at all, the
// exact "a whole file's worth of state stories vanishes from the sweep" gap M1(a) closed for the
// sibling case (a meta object present but with no literal `meta.id`). RED against pre-fix code:
// `work.unkeyable` was `undefined` and `work.measurable`/`work.notMeasurable` were both `[]` rather
// than throwing — confirmed by running this exact test before `extractFileStoryStates` was made to
// throw on a missing meta object.
test('buildStoryFileWork: a file with no meta object at all is reported as unkeyable, not silently emptied', () => {
  const source = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { Widget } from './index'

type Story = StoryObj<typeof Widget>

export const Hover: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`
  const filePath = path.join(rootDir, 'src/primitives/Widget/Widget.stories.tsx')
  const work = buildStoryFileWork(filePath, source)
  assert.ok(work.unkeyable, 'expected an unkeyable result')
  assert.equal(work.unkeyable.file, 'src/primitives/Widget/Widget.stories.tsx')
  assert.match(work.unkeyable.detail, /no default-exported meta object found/)
  assert.equal(work.measurable, undefined)
  assert.equal(work.notMeasurable, undefined)
})

test('buildStoryFileWork: a keyable file splits its state stories into measurable and notMeasurable', () => {
  const source = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { Widget } from './index'

const meta: Meta<typeof Widget> = {
  id: 'primitives-widget',
  title: 'Primitives/Widget',
  component: Widget,
}

export default meta
type Story = StoryObj<typeof Widget>

export const Hover: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const MysteryFocus: Story = {
  play: async ({ canvasElement }) => {
    const el = canvasElement.querySelector('.mystery')
    el.focus()
  },
}

export const Primary: Story = {
  args: { variant: 'primary' },
}
`
  const filePath = path.join(rootDir, 'src/primitives/Widget/Widget.stories.tsx')
  const work = buildStoryFileWork(filePath, source)
  assert.equal(work.unkeyable, undefined)
  assert.deepEqual(
    work.measurable.map((m) => m.exportName),
    ['Hover'],
  )
  assert.deepEqual(
    work.notMeasurable.map((m) => m.exportName),
    ['MysteryFocus'],
  )
  assert.equal(work.notMeasurable[0].reason, 'play-focus-target-unresolved')
})

// --- T679: discovery is the built Storybook index, not a first-file-per-directory walk ------------
// Filed from the adversarial review of #105 (F6): a second `*.stories.tsx` in one component
// directory, or a state story outside the three tiers (`.storybook/foundations/`), was not swept
// or reported. The cases below plant those shapes in a virtual index + virtual
// sources and assert they are swept or fail the gate, named.

const WIDGET_STORIES = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { Widget } from './index'

const meta: Meta<typeof Widget> = { id: 'primitives-widget', title: 'Primitives/Widget', component: Widget }
export default meta
type Story = StoryObj<typeof Widget>

export const Primary: Story = { args: { variant: 'primary' } }
`

// A second story file in the same directory, carrying a state story the old first-file-wins walk
// did not read.
const WIDGET_STATES_STORIES = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { Widget } from './index'

const meta: Meta<typeof Widget> = { id: 'primitives-widget-states', title: 'Primitives/Widget states', component: Widget }
export default meta
type Story = StoryObj<typeof Widget>

export const Hover: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`

// A componentless foundations page (no `component`, no `id`): keyed from its title.
const FOUNDATION_STORIES = `
import type { Meta, StoryObj } from '@storybook/react-vite'

const meta: Meta = { title: 'Foundations/Pressed', parameters: { layout: 'fullscreen' } }
export default meta
type Story = StoryObj

export const Overview: Story = { render: () => null }
export const Pressed: Story = {
  parameters: { visualForceState: { state: 'active', role: 'button' } },
}
`

function indexOf(entries) {
  return {
    v: 5,
    entries: Object.fromEntries(
      entries.map(([id, importPath, type = 'story']) => [id, { id, type, importPath }]),
    ),
  }
}

function sourcesOf(files) {
  return (filePath) => {
    const rel = path.relative(dsDir, filePath).split(path.sep).join('/')
    if (!(rel in files)) throw new Error(`ENOENT: ${rel}`)
    return files[rel]
  }
}

const WIDGET_FILE = 'src/primitives/Widget/Widget.stories.tsx'
const WIDGET_STATES_FILE = 'src/primitives/Widget/WidgetStates.stories.tsx'
const FOUNDATION_FILE = '.storybook/foundations/Pressed.stories.tsx'

test('buildStateSignalWork: a second story file in one directory is swept, not skipped', () => {
  const index = indexOf([
    ['primitives-widget--primary', `./${WIDGET_FILE}`],
    ['primitives-widget-states--hover', `./${WIDGET_STATES_FILE}`],
  ])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({
      [WIDGET_FILE]: WIDGET_STORIES,
      [WIDGET_STATES_FILE]: WIDGET_STATES_STORIES,
    }),
    diskFiles: [WIDGET_FILE, WIDGET_STATES_FILE],
  })
  assert.deepEqual(
    work.measurable.map((m) => m.stateId),
    ['primitives-widget-states--hover'],
  )
  assert.deepEqual(work.discoveryGaps, [])
  assert.deepEqual(work.unkeyableFiles, [])
  assert.equal(work.filesDiscovered, 2)
  assert.equal(work.indexedStoryCount, 2)
})

test('buildStateSignalWork: a state story outside the three tiers (foundations) is swept', () => {
  const index = indexOf([
    ['foundations-pressed--overview', `./${FOUNDATION_FILE}`],
    ['foundations-pressed--pressed', `./${FOUNDATION_FILE}`],
  ])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({ [FOUNDATION_FILE]: FOUNDATION_STORIES }),
    diskFiles: [FOUNDATION_FILE],
  })
  assert.deepEqual(
    work.measurable.map((m) => m.stateId),
    ['foundations-pressed--pressed'],
  )
  assert.deepEqual(work.discoveryGaps, [])
  assert.deepEqual(work.unkeyableFiles, [])
})

test('buildStateSignalWork: contrast — one story file with only a non-state story flags nothing', () => {
  const index = indexOf([
    ['primitives-widget--primary', `./${WIDGET_FILE}`],
    ['primitives-widget--docs', `./${WIDGET_FILE}`, 'docs'],
  ])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({ [WIDGET_FILE]: WIDGET_STORIES }),
    diskFiles: [WIDGET_FILE],
  })
  assert.deepEqual(work.measurable, [])
  assert.deepEqual(work.notMeasurable, [])
  assert.deepEqual(work.discoveryGaps, [])
  assert.deepEqual(work.unkeyableFiles, [])
  assert.equal(work.indexedStoryCount, 1, 'a docs entry is not a story')
})

test('buildStateSignalWork: a story file on disk that the index does not list fails, named', () => {
  // A stale build predating WidgetStates.stories.tsx: enumerating the index alone cannot see it.
  const index = indexOf([['primitives-widget--primary', `./${WIDGET_FILE}`]])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({
      [WIDGET_FILE]: WIDGET_STORIES,
      [WIDGET_STATES_FILE]: WIDGET_STATES_STORIES,
    }),
    diskFiles: [WIDGET_FILE, WIDGET_STATES_FILE],
  })
  assert.equal(work.discoveryGaps.length, 1)
  assert.equal(work.discoveryGaps[0].kind, 'story-file-not-indexed')
  assert.equal(work.discoveryGaps[0].file, WIDGET_STATES_FILE)
  const gate = decideSweepGate({
    classified: [entry('x', 'defended')],
    measurableCount: 1,
    discoveryGaps: work.discoveryGaps,
  })
  assert.equal(gate.pass, false)
  assert.equal(gate.failures[0].kind, 'discovery-gap')
  assert.equal(gate.failures[0].bucket, 'discovery-gap:story-file-not-indexed')
  assert.equal(gate.failures[0].file, WIDGET_STATES_FILE)
})

test('buildStateSignalWork: a state story the index does not list (stale build) fails, named', () => {
  const index = indexOf([['primitives-widget-states--other', `./${WIDGET_STATES_FILE}`]])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({ [WIDGET_STATES_FILE]: WIDGET_STATES_STORIES }),
    diskFiles: [WIDGET_STATES_FILE],
  })
  const kinds = work.discoveryGaps.map((g) => `${g.kind}:${g.stateId}`).sort()
  assert.deepEqual(kinds, [
    'indexed-story-not-parsed:primitives-widget-states--other',
    'state-story-not-indexed:primitives-widget-states--hover',
  ])
})

test('buildStateSignalWork: an index-listed story the parse never produced fails, named', () => {
  // `Computed` is exported through a call, not an object literal — the parse cannot see it, so it
  // cannot say whether it is a state story; the gate must not guess "no".
  const source = `${WIDGET_STORIES}\nexport const Computed = makeStory({ parameters: { visualForceState: { state: 'hover', role: 'button' } } })\n`
  const index = indexOf([
    ['primitives-widget--primary', `./${WIDGET_FILE}`],
    ['primitives-widget--computed', `./${WIDGET_FILE}`],
  ])
  const work = buildStateSignalWork({
    index,
    readSource: sourcesOf({ [WIDGET_FILE]: source }),
    diskFiles: [WIDGET_FILE],
  })
  assert.equal(work.discoveryGaps.length, 1)
  assert.equal(work.discoveryGaps[0].kind, 'indexed-story-not-parsed')
  assert.equal(work.discoveryGaps[0].stateId, 'primitives-widget--computed')
})

test('buildStateSignalWork: an index-listed file that cannot be read fails, named', () => {
  const index = indexOf([['primitives-widget--primary', `./${WIDGET_FILE}`]])
  const work = buildStateSignalWork({ index, readSource: sourcesOf({}), diskFiles: [] })
  assert.equal(work.discoveryGaps.length, 1)
  assert.equal(work.discoveryGaps[0].kind, 'unreadable-story-file')
  assert.equal(work.discoveryGaps[0].file, WIDGET_FILE)
})

test('reconcileFile / findUnindexedStoryFiles: equal sets produce no gap', () => {
  const parsed = buildStoryFileWork(path.join(dsDir, WIDGET_STATES_FILE), WIDGET_STATES_STORIES)
  assert.deepEqual(
    reconcileFile({
      file: WIDGET_STATES_FILE,
      indexedIds: ['primitives-widget-states--hover'],
      parsed,
    }),
    [],
  )
  assert.deepEqual(
    findUnindexedStoryFiles({ indexedFiles: [WIDGET_FILE].values(), diskFiles: [WIDGET_FILE] }),
    [],
  )
})

test('groupIndexByFile: groups story ids by importPath, ignores docs entries, strips ./', () => {
  const grouped = groupIndexByFile(
    indexOf([
      ['b--one', './src/b.stories.tsx'],
      ['a--one', './src/a.stories.tsx'],
      ['a--two', './src/a.stories.tsx'],
      ['a--docs', './src/a.stories.tsx', 'docs'],
    ]),
  )
  assert.deepEqual(
    [...grouped.entries()],
    [
      ['src/a.stories.tsx', ['a--one', 'a--two']],
      ['src/b.stories.tsx', ['b--one']],
    ],
  )
})

test('listStoryFilesOnDisk: finds every story file in a directory and under foundations, skips node_modules', () => {
  const base = mkdtempSync(path.join(tmpdir(), 'story-disk-'))
  try {
    for (const rel of [
      WIDGET_FILE,
      WIDGET_STATES_FILE,
      'src/primitives/Widget/index.tsx',
      FOUNDATION_FILE,
      'src/composites/Card/node_modules/dep/Dep.stories.tsx',
    ]) {
      mkdirSync(path.dirname(path.join(base, rel)), { recursive: true })
      writeFileSync(path.join(base, rel), '')
    }
    assert.deepEqual(
      listStoryFilesOnDisk(base),
      [FOUNDATION_FILE, WIDGET_FILE, WIDGET_STATES_FILE].sort(),
    )
  } finally {
    rmSync(base, { recursive: true, force: true })
  }
})

test('extractFileStoryStates: a componentless page is keyed by its literal title', () => {
  const result = extractFileStoryStates(path.join(dsDir, FOUNDATION_FILE), FOUNDATION_STORIES)
  assert.equal(result.kind, 'Foundations/Pressed')
  assert.deepEqual(
    result.stories.map((s) => s.id),
    ['foundations-pressed--overview', 'foundations-pressed--pressed'],
  )
})

// Review of #108 (M1): "componentless" used to be decided by `findMeta` finding nothing, and
// `findMeta` only recognises a top-level const whose initializer is a bare object literal with a
// `component` key. A component file written any other way (`satisfies`, `as`, an inline default
// export) was therefore treated as componentless and keyed by its title — silently, where before
// T679 it failed the gate as unkeyable. The rule is now decided from the default-exported meta
// object itself: a `component` key makes the file a component file.
const STORY_PATH = path.join(rootDir, 'src/primitives/Widget/Widget.stories.tsx')
const COMPONENT_STORIES_BODY = `
export const Hover = {
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`
const NO_ID_COMPONENT_SYNTAXES = {
  'const + satisfies': `
const meta = { title: 'Primitives/Widget', component: Widget } satisfies Meta<typeof Widget>
export default meta
${COMPONENT_STORIES_BODY}`,
  'inline export default': `
export default { title: 'Primitives/Widget', component: Widget }
${COMPONENT_STORIES_BODY}`,
  'inline export default + as': `
export default { title: 'Primitives/Widget', component: Widget } as Meta<typeof Widget>
${COMPONENT_STORIES_BODY}`,
  'inline export default + satisfies': `
export default { title: 'Primitives/Widget', component: Widget } satisfies Meta<typeof Widget>
${COMPONENT_STORIES_BODY}`,
  'const + as': `
const meta = { title: 'Primitives/Widget', component: Widget } as Meta<typeof Widget>
export default meta
${COMPONENT_STORIES_BODY}`,
  'const + type annotation': `
const meta: Meta<typeof Widget> = { title: 'Primitives/Widget', component: Widget }
export default meta
${COMPONENT_STORIES_BODY}`,
  'const + parenthesised satisfies': `
const meta = ({ title: 'Primitives/Widget', component: Widget } satisfies Meta<typeof Widget>)
export default meta
${COMPONENT_STORIES_BODY}`,
  'export { meta as default }': `
const meta = { title: 'Primitives/Widget', component: Widget } satisfies Meta<typeof Widget>
export { meta as default }
${COMPONENT_STORIES_BODY}`,
  'string-literal "component" key': `
export default { title: 'Primitives/Widget', 'component': Widget }
${COMPONENT_STORIES_BODY}`,
  'component arriving through a spread': `
const base = defineBase(Widget)
export default { title: 'Primitives/Widget', ...base }
${COMPONENT_STORIES_BODY}`,
}

for (const [syntax, body] of Object.entries(NO_ID_COMPONENT_SYNTAXES)) {
  test(`buildStoryFileWork: a component meta with no literal id is unkeyable, never keyed by title — ${syntax}`, () => {
    const work = buildStoryFileWork(STORY_PATH, body)
    assert.ok(work.unkeyable, `expected an unkeyable result for: ${syntax}`)
    assert.match(work.unkeyable.detail, /no string-literal "id"/)
    assert.equal(work.measurable, undefined)
  })
}

// Contrast: the same syntaxes, componentless, still key by title — the strict rule does not
// reach the foundations pages.
const COMPONENTLESS_SYNTAXES = {
  'const + satisfies': `
const meta = { title: 'Foundations/Pressed', parameters: {} } satisfies Meta
export default meta
${COMPONENT_STORIES_BODY}`,
  'inline export default': `
export default { title: 'Foundations/Pressed', parameters: {} }
${COMPONENT_STORIES_BODY}`,
  'inline export default + as': `
export default { title: 'Foundations/Pressed' } as Meta
${COMPONENT_STORIES_BODY}`,
  'const + type annotation': `
const meta: Meta = { title: 'Foundations/Pressed' }
export default meta
${COMPONENT_STORIES_BODY}`,
  'export { meta as default }': `
const meta = { title: 'Foundations/Pressed' } satisfies Meta
export { meta as default }
${COMPONENT_STORIES_BODY}`,
}

for (const [syntax, body] of Object.entries(COMPONENTLESS_SYNTAXES)) {
  test(`buildStoryFileWork: contrast — a componentless page still keys by its literal title — ${syntax}`, () => {
    const work = buildStoryFileWork(STORY_PATH, body)
    assert.equal(work.unkeyable, undefined, work.unkeyable?.detail)
    assert.deepEqual(work.storyIds, ['foundations-pressed--hover'])
  })
}

test('buildStoryFileWork: the plain "const meta: Meta<...> = {...}" component file with no id stays unkeyable', () => {
  const work = buildStoryFileWork(
    STORY_PATH,
    `
const meta: Meta<typeof Widget> = { title: 'Primitives/Widget', component: Widget }
export default meta
${COMPONENT_STORIES_BODY}`,
  )
  assert.ok(work.unkeyable)
  assert.match(work.unkeyable.detail, /no string-literal "id"/)
})

test('buildStoryFileWork: a component meta with a literal id keys by it, whatever the syntax', () => {
  const work = buildStoryFileWork(
    STORY_PATH,
    `
export default { id: 'primitives-widget', title: 'Primitives/Widget', component: Widget } satisfies Meta<typeof Widget>
${COMPONENT_STORIES_BODY}`,
  )
  assert.equal(work.unkeyable, undefined)
  assert.deepEqual(work.storyIds, ['primitives-widget--hover'])
})

test('buildStoryFileWork: a componentless page with no literal title is unkeyable, and the error names "title"', () => {
  for (const body of [
    `export default { parameters: {} }\n${COMPONENT_STORIES_BODY}`,
    `export default { title: SOME_TITLE } satisfies Meta\n${COMPONENT_STORIES_BODY}`,
    `const meta: Meta = { parameters: {} }\nexport default meta\n${COMPONENT_STORIES_BODY}`,
  ]) {
    const work = buildStoryFileWork(STORY_PATH, body)
    assert.ok(work.unkeyable, `expected an unkeyable result for: ${body}`)
    assert.match(work.unkeyable.detail, /"title"/)
    assert.doesNotMatch(work.unkeyable.detail, /no string-literal "id"/)
  }
})

test('buildStoryFileWork: a componentless page whose own "id" is not a literal is unkeyable on "id", never keyed by title', () => {
  const work = buildStoryFileWork(
    STORY_PATH,
    `export default { id: PAGE_ID, title: 'Foundations/Pressed' } satisfies Meta\n${COMPONENT_STORIES_BODY}`,
  )
  assert.ok(work.unkeyable)
  assert.match(work.unkeyable.detail, /"id"/)
})

// Review of #108 (L3): `listStoryFilesOnDisk` walks story-file roots that `.storybook/main.ts`'s
// `stories` globs also name — a hand-copied second list. The tests below read the real `stories`
// array and compare it to what the walker reaches, so adding or removing a glob fails here.
const dsRequire = createRequire(path.join(dsDir, 'package.json'))
const ts = dsRequire('typescript')
const MAIN_TS_PATH = path.join(dsDir, '.storybook', 'main.ts')

// The `stories` array of a Storybook main.ts, as its string globs.
function storiesGlobsOf(mainTsText) {
  const sourceFile = ts.createSourceFile(
    'main.ts',
    mainTsText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  )
  let globs = null
  const visit = (node) => {
    if (
      ts.isPropertyAssignment(node) &&
      node.name.getText() === 'stories' &&
      ts.isArrayLiteralExpression(node.initializer)
    ) {
      globs = node.initializer.elements.map((el) => {
        assert.ok(
          ts.isStringLiteralLike(el),
          `stories entry is not a string literal: ${el.getText()}`,
        )
        return el.text
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  assert.ok(globs, 'no `stories` array found in main.ts')
  return globs
}

// The literal directory a glob starts from, relative to the package: `main.ts` sits in
// `.storybook/`, so its globs are relative to that directory; everything up to the first path
// segment carrying glob syntax is the base.
function globBaseDir(glob) {
  const relToPackage = path.posix.normalize(path.posix.join('.storybook', glob))
  const literal = []
  for (const segment of relToPackage.split('/')) {
    if (/[*?[\]{}()!+@]/.test(segment)) break
    literal.push(segment)
  }
  return literal.join('/')
}

function plantStoryFileUnder(base, dir) {
  const rel = path.posix.join(dir, 'Planted.stories.tsx')
  mkdirSync(path.dirname(path.join(base, rel)), { recursive: true })
  writeFileSync(path.join(base, rel), '')
  return rel
}

test("listStoryFilesOnDisk reaches the base directory of every glob in the real .storybook/main.ts's stories array", () => {
  const bases = storiesGlobsOf(readFileSync(MAIN_TS_PATH, 'utf8')).map(globBaseDir)
  assert.ok(bases.length > 0)
  const dir = mkdtempSync(path.join(tmpdir(), 'story-roots-'))
  try {
    const plantedFiles = bases.map((b) => plantStoryFileUnder(dir, b)).sort()
    assert.deepEqual(listStoryFilesOnDisk(dir), plantedFiles)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// The walker skips a dot-directory below a root, as a `**` glob does under picomatch's default
// `dot: false`, so a story file under one is not reported as missing from the index.
test('listStoryFilesOnDisk: a dot-directory below a root is not walked; an explicit dot-directory root still is', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'story-dot-'))
  try {
    for (const rel of [
      'src/x/.cache/A.stories.tsx',
      'src/.hidden/deep/B.stories.tsx',
      '.storybook/foundations/.draft/C.stories.tsx',
      'src/x/Visible.stories.tsx',
      '.storybook/foundations/Pressed.stories.tsx',
    ]) {
      mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true })
      writeFileSync(path.join(dir, rel), '')
    }
    assert.deepEqual(listStoryFilesOnDisk(dir), [
      '.storybook/foundations/Pressed.stories.tsx',
      'src/x/Visible.stories.tsx',
    ])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("the walker's roots equal the base directories of the real .storybook/main.ts stories globs", () => {
  const bases = storiesGlobsOf(readFileSync(MAIN_TS_PATH, 'utf8')).map(globBaseDir)
  assert.deepEqual([...STORY_WALK_ROOTS].sort(), [...bases].sort())
})

test("storiesGlobsOf / globBaseDir read a planted stories array's base directories, so the roots comparison can see a third glob or a removed one", () => {
  assert.deepEqual(
    storiesGlobsOf(
      `export default { stories: ['../src/**/*.stories.tsx', './foundations/**/*.stories.tsx', '../lib/**/*.stories.tsx'] }`,
    ).map(globBaseDir),
    ['src', '.storybook/foundations', 'lib'],
  )
  assert.deepEqual(
    storiesGlobsOf(`export default { stories: ['../src/**/*.stories.tsx'] }`).map(globBaseDir),
    ['src'],
  )
})

// Review of #108 (finding 3): the walker's file-name pattern is a second fact `.storybook/main.ts`
// owns (the extensions its globs match), next to the base directories above. The walker takes the
// set as an argument; the first test derives it from a planted glob, and the second pins the
// walker's default to the real globs.
function storyExtensionsOfGlobs(globs) {
  const extensions = new Set()
  for (const glob of globs) {
    const match = /^\*\.stories\.(?:@\(([^)]+)\)|([A-Za-z0-9]+))$/.exec(glob.split('/').at(-1))
    assert.ok(match, `story file pattern not recognised in glob: ${glob}`)
    for (const extension of (match[1] ?? match[2]).split('|')) extensions.add(extension)
  }
  return [...extensions].sort()
}

test('listStoryFilesOnDisk: lists the extensions a planted glob names, and not index.tsx or a test file', () => {
  const extensions = storyExtensionsOfGlobs(
    storiesGlobsOf(`export default { stories: ['../src/**/*.stories.@(js|ts|tsx)'] }`),
  )
  assert.deepEqual(extensions, ['js', 'ts', 'tsx'])
  const dir = mkdtempSync(path.join(tmpdir(), 'story-ext-'))
  try {
    for (const rel of [
      'src/a/Foo.stories.js',
      'src/a/Foo.stories.ts',
      'src/a/Bar.stories.tsx',
      'src/a/index.tsx',
      'src/a/Foo.test.tsx',
      'src/a/Foo.stories.tsx.snap',
      'src/a/Foo.stories.mdx',
    ]) {
      mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true })
      writeFileSync(path.join(dir, rel), '')
    }
    assert.deepEqual(listStoryFilesOnDisk(dir, { extensions }), [
      'src/a/Bar.stories.tsx',
      'src/a/Foo.stories.js',
      'src/a/Foo.stories.ts',
    ])
    // Contrast: with the set the real globs name, the `.js` file is not a story file.
    assert.deepEqual(listStoryFilesOnDisk(dir, { extensions: ['ts', 'tsx'] }), [
      'src/a/Bar.stories.tsx',
      'src/a/Foo.stories.ts',
    ])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("the walker's default extensions equal those the real .storybook/main.ts stories globs match", () => {
  assert.deepEqual(
    [...STORY_FILE_EXTENSIONS].sort(),
    storyExtensionsOfGlobs(storiesGlobsOf(readFileSync(MAIN_TS_PATH, 'utf8'))),
  )
})

// Review of #108 (finding 7): a missing root is an empty listing; any other read error propagates.
function plantedDir(files) {
  const dir = mkdtempSync(path.join(tmpdir(), 'story-walk-'))
  for (const rel of files) {
    mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true })
    writeFileSync(path.join(dir, rel), '')
  }
  return dir
}

test('listStoryFilesOnDisk: a missing root is an empty listing, not an error', () => {
  const dir = plantedDir([])
  try {
    assert.deepEqual(listStoryFilesOnDisk(dir), [])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('listStoryFilesOnDisk: a root that is not a directory rethrows (ENOTDIR)', () => {
  const dir = plantedDir(['src'])
  try {
    assert.throws(() => listStoryFilesOnDisk(dir), { code: 'ENOTDIR' })
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('listStoryFilesOnDisk: an unreadable directory rethrows, at a root and below one', () => {
  const dir = plantedDir(['src/a/Foo.stories.tsx'])
  try {
    const denied = (blocked) => (target, options) => {
      if (path.relative(dir, target) === blocked) {
        throw Object.assign(new Error(`EACCES: permission denied, scandir '${target}'`), {
          code: 'EACCES',
        })
      }
      return readdirSync(target, options)
    }
    assert.throws(() => listStoryFilesOnDisk(dir, { readdir: denied('src') }), { code: 'EACCES' })
    assert.throws(() => listStoryFilesOnDisk(dir, { readdir: denied('src/a') }), {
      code: 'EACCES',
    })
    // Contrast: the same injected reader with nothing blocked lists the file.
    assert.deepEqual(listStoryFilesOnDisk(dir, { readdir: denied('nowhere') }), [
      'src/a/Foo.stories.tsx',
    ])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('listStoryFilesOnDisk: a directory that vanishes below a root rethrows (ENOENT is swallowed for a root alone)', () => {
  const dir = plantedDir(['src/a/Foo.stories.tsx'])
  try {
    const vanishing = (target, options) => {
      if (path.relative(dir, target) === 'src/a') {
        throw Object.assign(new Error(`ENOENT: no such file or directory, scandir '${target}'`), {
          code: 'ENOENT',
        })
      }
      return readdirSync(target, options)
    }
    assert.throws(() => listStoryFilesOnDisk(dir, { readdir: vanishing }), { code: 'ENOENT' })
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// Review of #108 (finding 5): a default export that does not resolve to an object literal here
// (an import, a call) leaves the file unkeyable. Another object in the file that happens to carry a
// `component` key is not the meta Storybook reads, so it must not stand in for it.
const UNRESOLVABLE_DEFAULT_EXPORTS = {
  'imported meta, with a decoy component object in the file': `
import meta from './shared'
const helper = { component: Other, id: 'composite-other' }
export default meta
${COMPONENT_STORIES_BODY}`,
  'a call': `
const decoy = { component: Other, id: 'composite-other' }
export default defineMeta(decoy)
${COMPONENT_STORIES_BODY}`,
  'a re-export of another module default': `
const decoy = { component: Other, id: 'composite-other' }
export { default } from './shared'
${COMPONENT_STORIES_BODY}`,
  'a renamed re-export of another module export': `
const decoy = { component: Other, id: 'composite-other' }
export { meta as default } from './shared'
${COMPONENT_STORIES_BODY}`,
  'a default-exported function': `
const decoy = { component: Other, id: 'composite-other' }
export default function meta() {}
${COMPONENT_STORIES_BODY}`,
}

for (const [shape, body] of Object.entries(UNRESOLVABLE_DEFAULT_EXPORTS)) {
  test(`buildStoryFileWork: an unresolvable default export is unkeyable, naming it, never keyed by another object — ${shape}`, () => {
    const work = buildStoryFileWork(STORY_PATH, body)
    assert.ok(work.unkeyable, `expected an unkeyable result for: ${shape}`)
    assert.match(work.unkeyable.detail, /default export/)
    assert.match(work.unkeyable.detail, /does not resolve to an object literal/)
    assert.equal(work.storyIds, undefined)
  })
}

test('buildStoryFileWork: a file with a decoy component object and no default export at all is unkeyable', () => {
  const work = buildStoryFileWork(
    STORY_PATH,
    `const decoy = { component: Other, id: 'composite-other' }\n${COMPONENT_STORIES_BODY}`,
  )
  assert.ok(work.unkeyable)
  assert.match(work.unkeyable.detail, /no default-exported meta object found/)
})

// Review of #108 (finding 2): the two modes differ on a missing Storybook build. The
// sweep's work list comes from the built index, so with none it has measured nothing and fails;
// the ordinary run has nothing to test and exits 0.
test('decideMissingIndex: the sweep with no index fails with exit 1, naming the build command', () => {
  const decision = decideMissingIndex({ indexExists: false, sweepMode: true })
  assert.equal(decision.proceed, false)
  assert.equal(decision.exitCode, 1)
  assert.ok(decision.message.includes(BUILD_STORYBOOK_COMMAND), decision.message)
  assert.match(decision.message, /gate failed/)
})

test('decideMissingIndex: contrast — an ordinary run with no index exits 0, naming the build command', () => {
  const decision = decideMissingIndex({ indexExists: false, sweepMode: false })
  assert.equal(decision.proceed, false)
  assert.equal(decision.exitCode, 0)
  assert.ok(decision.message.includes(BUILD_STORYBOOK_COMMAND), decision.message)
  assert.doesNotMatch(decision.message, /gate failed/)
})

test('decideMissingIndex: with an index, either mode proceeds and exits nothing', () => {
  for (const sweepMode of [true, false]) {
    const decision = decideMissingIndex({ indexExists: true, sweepMode })
    assert.equal(decision.proceed, true)
    assert.equal(decision.exitCode, undefined)
    assert.equal(decision.message, undefined)
  }
})

test('parseSweepIndex: valid JSON with at least one story is returned as parsed', () => {
  const index = indexOf([['a--one', './src/a.stories.tsx']])
  assert.deepEqual(parseSweepIndex(JSON.stringify(index)), index)
})

test('parseSweepIndex: unparseable text, a shape without entries, and an index with no story all throw', () => {
  assert.throws(() => parseSweepIndex('{ not json'), /not valid JSON/)
  assert.throws(() => parseSweepIndex('{}'), /lists no story/)
  assert.throws(() => parseSweepIndex(JSON.stringify(indexOf([]))), /lists no story/)
  // Docs entries are not stories: an index of docs alone has nothing to sweep.
  assert.throws(
    () => parseSweepIndex(JSON.stringify(indexOf([['a--docs', './src/a.mdx', 'docs']]))),
    /lists no story/,
  )
})
