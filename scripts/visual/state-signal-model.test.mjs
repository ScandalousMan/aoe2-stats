// T675 (slice 2/N): unit tests for state-signal-model.mjs's own pure parts — self-pairing and
// bucket classification never touch a filesystem or a browser, so both are provable against small,
// hand-written fixtures rather than the real tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractFileStoryStates,
  planSelfRest,
  classifyBucket,
  extractVisualCaptureClip,
  decideSweepGate,
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
    parts: [{ selector: undefined, role: 'button', name: 'Manage', nth: undefined }],
    pad: '2',
  })
})

test('extractVisualCaptureClip resolves a part role annotated "as const", not only a bare literal', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('RoleAsConstClip').clip, {
    parts: [{ selector: undefined, role: 'link', name: undefined, nth: undefined }],
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
    parts: [{ selector: undefined, role: 'button', name: 'Manage', nth: undefined }],
    pad: '2',
  })
})

test('extractVisualCaptureClip resolves a clip written inline and annotated "as const", not only one referenced by identifier', () => {
  const { byName } = fixtureStories()
  assert.deepEqual(byName.get('InlineAsConstClip').clip, {
    parts: [{ selector: undefined, role: 'button', name: 'Manage', nth: undefined }],
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
// T675 slice 4b: the sweep is a gate, not only a report. Every one of `classifyBucket`'s eight
// buckets is exercised once here, on a minimal `{ stateId, bucket }` shape — `decideSweepGate` reads
// only `bucket`, never the unit-level detail `classifyBucket` itself already owns and this file's
// own tests above already cover.
function entry(stateId, bucket) {
  return { stateId, bucket }
}

test('decideSweepGate: defended and defended-without-clip both pass', () => {
  const classified = [entry('a', 'defended'), entry('b', 'defended-without-clip')]
  assert.deepEqual(decideSweepGate(classified), { pass: true, failures: [] })
})

test('decideSweepGate: dimension-mismatch passes — a size change fails toHaveScreenshot by construction', () => {
  const classified = [entry('a', 'dimension-mismatch')]
  assert.deepEqual(decideSweepGate(classified), { pass: true, failures: [] })
})

test('decideSweepGate: zero and zero-despite-clip both fail, named', () => {
  const classified = [entry('a', 'zero'), entry('b', 'zero-despite-clip')]
  const result = decideSweepGate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['a', 'b'],
  )
})

test('decideSweepGate: clip-fixes and clipped-still-under-threshold both fail — a real signal that still does not clear the comparator', () => {
  const classified = [entry('a', 'clip-fixes'), entry('b', 'clipped-still-under-threshold')]
  const result = decideSweepGate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['a', 'b'],
  )
})

test('decideSweepGate: state-not-reproduced fails — the sweep could not confirm the frame it measured', () => {
  const classified = [entry('a', 'state-not-reproduced')]
  const result = decideSweepGate(classified)
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
  const result = decideSweepGate(classified)
  assert.equal(result.pass, false)
  assert.deepEqual(
    result.failures.map((f) => f.stateId),
    ['bad'],
  )
})

test('decideSweepGate: empty input passes vacuously — nothing measured is nothing left undefended', () => {
  assert.deepEqual(decideSweepGate([]), { pass: true, failures: [] })
})
