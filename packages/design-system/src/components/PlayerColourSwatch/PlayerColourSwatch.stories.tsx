import type { Meta, StoryObj } from '@storybook/react-vite'
import { PlayerColourSwatch } from './index'

const meta: Meta<typeof PlayerColourSwatch> = {
  title: 'Composite/PlayerColourSwatch',
  component: PlayerColourSwatch,
}

export default meta
type Story = StoryObj<typeof PlayerColourSwatch>

export const Blue: Story = {
  args: { colorId: 1, playerName: 'GL.TheViper' },
}

export const SizeXs: Story = {
  name: 'Size — xs (12px, default, MatchRow)',
  args: { colorId: 2, playerName: 'Hera', size: 'xs' },
}

export const SizeSm: Story = {
  name: 'Size — sm (16px, MatchDetailPanel participants table)',
  args: { colorId: 2, playerName: 'Hera', size: 'sm' },
}

// §9 acceptance — all eight colours, each beside a name, in one frame.
export const AllEightColours: Story = {
  name: 'All eight colours, each beside a name',
  render: () => (
    <ul className="flex flex-col gap-3">
      {(
        [
          [1, 'Blue player'],
          [2, 'Red player'],
          [3, 'Green player'],
          [4, 'Yellow player'],
          [5, 'Teal player'],
          [6, 'Purple player'],
          [7, 'Grey player'],
          [8, 'Orange player'],
        ] as const
      ).map(([colorId, name]) => (
        <li key={colorId} className="flex items-center gap-2">
          <PlayerColourSwatch colorId={colorId} playerName={name} />
          <span>{name}</span>
        </li>
      ))}
    </ul>
  ),
}

// §4 "empty" — `colorId` is `null`: companion never heard of this match, a legitimate resting
// state (data-model.md §6), not a migration in progress.
export const NotRecorded: Story = {
  name: 'Empty — colorId null (companion never heard of this match)',
  render: () => (
    <div className="flex items-center gap-2">
      <PlayerColourSwatch colorId={null} playerName="Some player" />
      <span>Some player</span>
    </div>
  ),
}

// §4 "error" — outside 1..8. Must render byte-identically to NotRecorded above: same neutral
// chip, same hidden text, never a red/error tone.
export const OutOfRange: Story = {
  name: 'Error — colorId 99, out of range (must render identically to the empty story above)',
  render: () => (
    <div className="flex items-center gap-2">
      <PlayerColourSwatch colorId={99} playerName="Some player" />
      <span>Some player</span>
    </div>
  ),
}

// §2a — the chip never renders without a name beside it. `playerName` blank renders nothing.
export const BlankPlayerName: Story = {
  name: 'Blank playerName — renders nothing where the chip would be',
  render: () => (
    <div className="rounded-sm border border-dashed border-border p-4 font-sans text-xs text-text-secondary">
      Nothing renders below this line —{' '}
      <span className="inline-block align-middle">
        <PlayerColourSwatch colorId={1} playerName="" />
      </span>
    </div>
  ),
}

// A coloured row and a neutral row together — checks alignment stays identical whether or not the
// colour is recorded (§9 acceptance).
export const ColouredAndNeutralAligned: Story = {
  name: 'Coloured and neutral rows, checking alignment',
  render: () => (
    <ul className="flex flex-col gap-2">
      <li className="flex items-center gap-2">
        <PlayerColourSwatch colorId={4} playerName="Yellow player" />
        <span>Yellow player</span>
      </li>
      <li className="flex items-center gap-2">
        <PlayerColourSwatch colorId={null} playerName="Unrecorded player" />
        <span>Unrecorded player</span>
      </li>
    </ul>
  ),
}
