// T675 (slice 1/N): unit tests for state-signal-model.mjs's own pure parts — pairing and bucket
// classification never touch a filesystem or a browser, so both are provable against small,
// hand-written fixtures rather than the real tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractFileStoryStates,
  argsTextMapsEqual,
  pairRestingStory,
  classifyBucket,
  extractVisualCaptureClip,
} from './state-signal-model.mjs'

// A minimal CSF file exercising: a plain rest story, a forced-hover sibling with identical args
// (the real pairing case), a forced story whose own args carry an extra key no sibling shares (this
// task's own named trap — comparing a `size: 'lg'` story against a `md`-implicit one), a clipped
// forced story whose args match the plain rest exactly, and a spread-args pair
// (`...shared, extra: 1`) so `argsTextMapsEqual` is proven against the spread-expansion path too.
const FIXTURE_SOURCE = `
import type { Meta, StoryObj } from '@storybook/react-vite'
import { Widget } from './index'

const shared = { onClick: () => {} }
const TRIGGER_CLIP = { parts: [{ role: 'button', name: 'Manage' }], pad: '2' }

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

export const PrimaryHoverMd: Story = {
  args: { variant: 'primary' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}

export const ClosedTrigger: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
}

export const TriggerFocusVisible: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button' },
    visualCaptureClip: { parts: [{ role: 'button', name: 'Manage' }], pad: '2' },
  },
}

// Dialog.stories.tsx's PRIMARY_ACTION_CLIP / Menu.stories.tsx's TRIGGER_CLIP shape: a top-level
// const referenced by identifier, never written inline — the real defect this fixture exists to
// pin (an earlier version of extractVisualCaptureClip only ever checked
// ts.isObjectLiteralExpression directly, which an identifier is not, so it silently read every
// by-reference clip in the tree as "no clip at all").
export const TriggerFocusVisibleByRef: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'button' },
    visualCaptureClip: TRIGGER_CLIP,
  },
}

// AccountErasurePanel.stories.tsx's own erasedScreenLinkClip shape: a clip part's own role
// annotated \`as const\` — the second real defect this fixture pins (literalOf used to read this
// back as "present but not a literal" and silently drop it).
const ROLE_AS_CONST_CLIP = { parts: [{ role: 'link' as const }], pad: '2' }

export const RoleAsConstClip: Story = {
  args: { variant: 'actions', triggerLabel: 'Manage' },
  parameters: {
    visualForceState: { state: 'hover', role: 'link' },
    visualCaptureClip: ROLE_AS_CONST_CLIP,
  },
}

export const SpreadRest: Story = {
  args: { ...shared, extra: 1 },
}

export const SpreadHover: Story = {
  args: { ...shared, extra: 1 },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
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
  assert.equal(byName.get('PrimaryHoverMd').id, 'primitives-widget--primary-hover-md')
})

test('extractFileStoryStates marks a forced story isStateStory and a plain one not', () => {
  const { byName } = fixtureStories()
  assert.equal(byName.get('Hover').isStateStory, true)
  assert.equal(byName.get('Primary').isStateStory, false)
})

test('extractVisualCaptureClip reads parts and pad; absent for an unclipped story', () => {
  const { byName } = fixtureStories()
  assert.equal(byName.get('Hover').clip, null)
  assert.deepEqual(byName.get('TriggerFocusVisible').clip, {
    parts: [{ selector: undefined, role: 'button', name: 'Manage', nth: undefined }],
    pad: '2',
  })
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

test('argsTextMapsEqual: identical merged args (meta default + story override) match', () => {
  const { byName } = fixtureStories()
  assert.equal(
    argsTextMapsEqual(byName.get('Primary').argsTextMap, byName.get('Hover').argsTextMap),
    true,
  )
})

test('argsTextMapsEqual: a key present on one side and absent on the other never matches — the size trap', () => {
  const { byName } = fixtureStories()
  // `Primary` carries `size: 'lg'`; `PrimaryHoverMd` omits `size` entirely (relies on the
  // component's own default) — this task's own named trap. Neither `Primary` nor any other sibling
  // in this fixture shares `PrimaryHoverMd`'s exact key set, so it must pair with nothing.
  assert.equal(
    argsTextMapsEqual(byName.get('Primary').argsTextMap, byName.get('PrimaryHoverMd').argsTextMap),
    false,
  )
})

test('argsTextMapsEqual: a spread of a top-level const object is expanded before comparing', () => {
  const { byName } = fixtureStories()
  assert.equal(
    argsTextMapsEqual(byName.get('SpreadRest').argsTextMap, byName.get('SpreadHover').argsTextMap),
    true,
  )
})

test('pairRestingStory: the real pairing case resolves to exactly one candidate', () => {
  const { result, byName } = fixtureStories()
  const pairing = pairRestingStory(byName.get('Hover'), result.stories)
  assert.equal(pairing.measurable, true)
  assert.equal(pairing.restStory.exportName, 'Primary')
})

test('pairRestingStory: no same-size rest exists — reported, never silently paired with a different size', () => {
  const { result, byName } = fixtureStories()
  const pairing = pairRestingStory(byName.get('PrimaryHoverMd'), result.stories)
  assert.equal(pairing.measurable, false)
  assert.equal(pairing.reason, 'no-same-args-sibling')
})

test('pairRestingStory: a clipped state pairs with an unclipped rest — the clip lives on the state story only', () => {
  const { result, byName } = fixtureStories()
  const stateStory = byName.get('TriggerFocusVisible')
  const pairing = pairRestingStory(stateStory, result.stories)
  assert.equal(pairing.measurable, true)
  assert.equal(pairing.restStory.exportName, 'ClosedTrigger')
  // The rest story itself carries no clip of its own — `state-signal-sweep.spec.ts` is what crops
  // its frame to the *state* story's clip rect at render time; this pure test only proves the pair
  // is found and that the asymmetry (state clipped, rest not) is real, not itself a pairing defect.
  assert.equal(stateStory.clip !== null, true)
  assert.equal(pairing.restStory.clip, null)
})

test('pairRestingStory: more than one same-args sibling is ambiguous, never guessed', () => {
  const source = `
    import type { Meta, StoryObj } from '@storybook/react-vite'
    import { Widget } from './index'
    const meta: Meta<typeof Widget> = { id: 'primitives-widget', title: 'Primitives/Widget', component: Widget }
    export default meta
    type Story = StoryObj<typeof Widget>
    export const A: Story = { args: { variant: 'x' } }
    export const B: Story = { args: { variant: 'x' } }
    export const Hover: Story = {
      args: { variant: 'x' },
      parameters: { visualForceState: { state: 'hover', role: 'button' } },
    }
  `
  const result = extractFileStoryStates('ambiguous.stories.tsx', source)
  const hover = result.stories.find((s) => s.exportName === 'Hover')
  const pairing = pairRestingStory(hover, result.stories)
  assert.equal(pairing.measurable, false)
  assert.equal(pairing.reason, 'ambiguous-siblings')
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
