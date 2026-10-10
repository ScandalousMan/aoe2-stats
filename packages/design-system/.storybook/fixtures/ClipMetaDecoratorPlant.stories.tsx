import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '../../src/primitives/Button'

// The meta-decorator clip plant of T703 (feature 005): a clip written by a decorator on the DEFAULT
// export, so it runs for every story of the file and no story object carries it. It sits in its own
// file because a decorator on the meta applies to every story beside it, and `./ClipPlants.stories.tsx`
// holds the contrasts that must record no clip. `tests/visual/state-coverage-runtime.spec.ts` asserts
// that the runtime pass records `clip: true` for it.
//
// Tagged `state-coverage-fixture`, `!dev` and `!autodocs`, like the plants beside this file.
const meta: Meta = {
  id: 'state-coverage-fixture-clip-meta-decorator',
  title: 'State coverage fixtures/Clip meta decorator',
  tags: ['state-coverage-fixture', '!dev', '!autodocs'],
  decorators: [
    (Story, { parameters }) => {
      parameters.visualCaptureClip = { parts: [{ role: 'button' }] }
      return <Story />
    },
  ],
}

export default meta
type Story = StoryObj

export const ClipFromMetaDecorator: Story = {
  render: () => (
    <Button variant="primary" size="md">
      Go
    </Button>
  ),
}
