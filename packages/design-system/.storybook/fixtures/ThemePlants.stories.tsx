import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../../src/primitives/Button'

// The theme plants of T710 (feature 005, `specs/005-design-system-foundations/tasks.md`): one story per
// way what a story renders depends on the theme, which the capture shows in BOTH (`stories.spec.ts`
// runs the light and the dark theme at every width). The runtime pass settles each story in both
// themes and credits what both show (`combineThemeRecords`, `tests/visual/state-coverage-runtime.ts`);
// `tests/visual/state-coverage-runtime.spec.ts` asserts the answer per plant. A pass that recorded the
// light render alone would credit a cell the dark capture does not show.
//
// Tagged `state-coverage-fixture`, `!dev` and `!autodocs`, like the plants beside this file
// (`./Plants.stories.tsx`): no sidebar entry, no docs page, never captured. Plain markup, no styling.
const meta: Meta = {
  id: 'state-coverage-fixture-theme-plants',
  title: 'State coverage fixtures/Theme plants',
  tags: ['state-coverage-fixture', '!dev', '!autodocs'],
}

export default meta
type Story = StoryObj

const go = (
  <Button variant="primary" size="md">
    Go
  </Button>
)

// A `<Button disabled>` the light theme mounts and the dark one does not: the light render alone shows a
// disabled Button, so no cell for it may be credited, and the `Button` both themes mount still is.
export const DisabledButtonInLightOnly: Story = {
  decorators: [
    (Story, { globals }) => (
      <>
        <Story />
        {globals.theme === 'light' && (
          <Button variant="ghost" size="lg" disabled>
            Off
          </Button>
        )}
      </>
    ),
  ],
  render: () => go,
}

// The contrast: the same disabled `Button` in both themes is what both captures show, so it is credited
// (the `disabledAt` of its instance names the stamp of the element the browser reports disabled).
export const DisabledButtonInBothThemes: Story = {
  render: () => (
    <>
      {go}
      <Button variant="ghost" size="lg" disabled>
        Off
      </Button>
    </>
  ),
}

// A force that finds one `Button` in the light theme and two in the dark one: neither answer is the
// capture's, so the record refuses the force.
export const ForceCountDiffersInDark: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Go' } },
  render: (_args, { globals }) => (
    <>
      {go}
      {globals.theme === 'dark' && go}
    </>
  ),
}

// A force that finds exactly one element in each theme, a different one: the `Button` in light, a raw
// `<button>` the story writes in dark. Both counts are one; the stamp and the placing instance are what
// the two records differ in.
export const ForceElementDiffersInDark: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Go' } },
  render: (_args, { globals }) =>
    globals.theme === 'dark' ? <button type="button">Go</button> : go,
}

// The contrast: the same forced `Button` in both themes. The two answers are equal, so the record is
// the ordinary one, with no `differsByTheme`.
export const ForceSameInBothThemes: Story = {
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Go' } },
  render: () => go,
}

// A `play()` that moves focus to the `Button` in the light theme only: the dark render shows no focus,
// so the record holds no focus (`focus: null`) and carries `focusDiffersByTheme`, on which the checker
// withholds the Rest credit of the story's own mounts.
export const FocusInLightOnly: Story = {
  play: ({ canvasElement, globals }) => {
    if (globals.theme === 'light') canvasElement.querySelector('button')?.focus()
  },
  render: () => go,
}

// The contrast: the same focus in both themes is in the record, with no `focusDiffersByTheme`.
export const FocusInBothThemes: Story = {
  play: ({ canvasElement }) => {
    canvasElement.querySelector('button')?.focus()
  },
  render: () => go,
}
