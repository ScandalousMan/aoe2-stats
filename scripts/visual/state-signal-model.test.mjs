// T675 (slice 2/N): unit tests for state-signal-model.mjs's own pure parts — self-pairing and
// bucket classification never touch a filesystem or a browser, so both are provable against small,
// hand-written fixtures rather than the real tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {
  extractFileStoryStates,
  planSelfRest,
  classifyBucket,
  extractVisualCaptureClip,
  decideSweepGate,
  buildStoryFileWork,
  rootDir,
} from './state-signal-model.mjs'

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
