import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../../src/primitives/Button'

// The clip plants of T703 (feature 005, `specs/005-design-system-foundations/tasks.md`): one story per
// way a `visualCaptureClip` reaches the capture without appearing in an object literal the static
// reading of `scripts/checks/state-coverage.mjs` could read. Storybook passes a story's `parameters`
// object to `play`, `loaders`, `beforeEach` and decorators through the story context, merges the
// deprecated `story.parameters`, and reads the object through its prototype chain; the capture
// (`readCaptureClip`, `tests/visual/story-render.ts`) reads the settled `story.parameters`. Each plant
// below sets a clip one of those ways, and `tests/visual/state-coverage-runtime.spec.ts` asserts that
// the runtime pass records `clip: true` for it. The two contrasts (`NoClip`, `FullPageTagged`) pin the
// other half: a story with no clip records `clip: false`, and a `visual-full-page` tag is recorded
// from the built index.
//
// The preview-level shapes of the same task (the preview's `parameters` mutated from another module,
// a `config.tsx` loaded in place of a preview, the preview mutating its own default export) cannot be
// a story: they are planted as manifest records in `scripts/checks/state-coverage.test.mjs`, where the
// record is what the check reads, whatever put the clip there.
//
// Tagged `state-coverage-fixture`, `!dev` and `!autodocs`, like the plants beside this file
// (`./Plants.stories.tsx`): no sidebar entry, no docs page, never captured. Plain markup, no styling.
const meta: Meta = {
  id: 'state-coverage-fixture-clip-plants',
  title: 'State coverage fixtures/Clip plants',
  tags: ['state-coverage-fixture', '!dev', '!autodocs'],
}

export default meta
type Story = StoryObj

const clip = () => ({ parts: [{ role: 'button' }] })
const render = () => (
  <Button variant="primary" size="md">
    Go
  </Button>
)

// The contrast: nothing sets a clip, so the record says none.
export const NoClip: Story = { render }

// The contrast for the other half of the frame: the built index tags it, the record says full-page.
export const FullPageTagged: Story = { tags: ['visual-full-page'], render }

// A clip written from `play()`, through the story context's `parameters`.
export const ClipFromPlay: Story = {
  render,
  play: ({ parameters }) => {
    parameters.visualCaptureClip = clip()
  },
}

// A clip written from a loader, through the story context's `parameters`.
export const ClipFromLoader: Story = {
  render,
  loaders: [
    ({ parameters }) => {
      parameters.visualCaptureClip = clip()
      return {}
    },
  ],
}

// A clip written by a story's own decorator, through the story context's `parameters`.
export const ClipFromDecorator: Story = {
  render,
  decorators: [
    (Story, { parameters }) => {
      parameters.visualCaptureClip = clip()
      return <Story />
    },
  ],
}

// A clip declared through the deprecated `story` annotation, which Storybook merges into the story's
// parameters; no `parameters` key of the story object carries it.
export const ClipFromStoryAnnotation = {
  render,
  story: { parameters: { visualCaptureClip: clip() } },
} as Story

// A clip declared under a `__proto__` key of the STORY object: an object literal's `__proto__` sets the
// prototype of the object rather than writing an own key, and Storybook reads the story's `parameters`
// through that chain, while a reader of the object literal sees an ordinary key.
export const ClipFromProto = {
  render,
  __proto__: { parameters: { visualCaptureClip: clip() } },
} as Story

// The contrast the same shape one level down: a `__proto__` key INSIDE `parameters` is lost by
// Storybook's own merge of the parameters (it copies own keys), so the capture takes no clip and the
// record says none. A static reading that refused it would be refusing a frame the capture shows whole.
export const ProtoInsideParametersNoClip: Story = {
  render,
  parameters: { __proto__: { visualCaptureClip: clip() } },
}

// A `visualCaptureClip` getter defined on `Object.prototype`, so every parameters object that has no
// clip of its own reads one. Defined from a loader: it runs in the story's own page, which a
// navigation to the next story discards.
export const ClipFromObjectPrototype: Story = {
  render,
  loaders: [
    () => {
      Object.defineProperty(Object.prototype, 'visualCaptureClip', {
        configurable: true,
        get: clip,
      })
      return {}
    },
  ],
}

// T706: a clip that depends on the theme. Decorators, loaders and `play` receive `context.globals`, and
// the capture (`tests/visual/stories.spec.ts`) runs both themes and reads the clip at each, so a clip
// applied in one theme only is a clip the capture shows. The record is the disjunction of the two
// themes: each of the three stories below records `clip: true`, whichever theme carries the clip.

// A story decorator that sets the clip only when the theme is dark: the light probe alone records none.
export const ClipOnlyInDark: Story = {
  render,
  decorators: [
    (Story, { parameters, globals }) => {
      if (globals.theme === 'dark') parameters.visualCaptureClip = clip()
      return <Story />
    },
  ],
}

// A clip literal that a decorator deletes unless the theme is dark: the light theme settles with no
// clip, the dark one with the literal in place.
export const ClipLiteralDeletedUnlessDark: Story = {
  render,
  parameters: { visualCaptureClip: clip() },
  decorators: [
    (Story, { parameters, globals }) => {
      if (globals.theme !== 'dark') delete parameters.visualCaptureClip
      return <Story />
    },
  ],
}

// The contrast: a clip set only in the light theme. The record is the disjunction, so it is `clip: true`
// too, and the dark probe adds nothing to it.
export const ClipOnlyInLight: Story = {
  render,
  decorators: [
    (Story, { parameters, globals }) => {
      if (globals.theme === 'light') parameters.visualCaptureClip = clip()
      return <Story />
    },
  ],
}

// T708: a clip that depends on storage the light settle wrote. `stories.spec.ts` gives every capture
// unit a fresh browser context, so the dark capture never sees what the light one wrote; the runtime
// pass reuses one page, so it clears cookies and both storages before each settle to start the way a
// capture unit does. The decorator writes a flag in the light theme and clips in the dark theme only
// while that flag is absent. With storage shared across the two settles the dark settle finds the flag
// and takes no clip (`clip: false`); with storage cleared per settle it clips (`clip: true`).
const STORAGE_FLAG = 'state-coverage-fixture-clip-storage-flag'
export const ClipOnlyInDarkWhileStorageFlagAbsent: Story = {
  render,
  decorators: [
    (Story, { parameters, globals }) => {
      if (globals.theme === 'light') {
        localStorage.setItem(STORAGE_FLAG, 'written-by-the-light-settle')
      } else if (globals.theme === 'dark' && localStorage.getItem(STORAGE_FLAG) === null) {
        parameters.visualCaptureClip = clip()
      }
      return <Story />
    },
  ],
}
