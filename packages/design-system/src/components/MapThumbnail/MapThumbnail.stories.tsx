import type { Meta, StoryObj } from '@storybook/react-vite'
import { Skeleton } from '../Skeleton'
import { MapThumbnail } from './index'

const meta: Meta<typeof MapThumbnail> = {
  title: 'Composite/MapThumbnail',
  component: MapThumbnail,
}

export default meta
type Story = StoryObj<typeof MapThumbnail>

const ARABIA_URL = '/game-assets/maps/arabia.webp'

export const Default: Story = {
  args: { thumbnailUrl: ARABIA_URL, mapName: 'Arabia' },
}

export const SizeSm: Story = {
  name: 'Size — sm (32px, MatchRow 1280 table row)',
  args: { thumbnailUrl: ARABIA_URL, mapName: 'Arabia', size: 'sm' },
}

export const SizeMd: Story = {
  name: 'Size — md (64px, default card layout)',
  args: { thumbnailUrl: ARABIA_URL, mapName: 'Arabia', size: 'md' },
}

export const SizeLg: Story = {
  name: 'Size — lg (96px, MatchDetailPanel header)',
  args: { thumbnailUrl: ARABIA_URL, mapName: 'Arabia', size: 'lg' },
}

export const AllSizes: Story = {
  name: 'All three sizes in one frame',
  render: () => (
    <div className="flex items-end gap-6">
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="sm" />
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="md" />
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="lg" />
    </div>
  ),
}

// §4 "empty" — a named map the pack does not cover (custom/tournament map): the designed degrade
// path (FR-010, FR-016), not a defect. No frame, no grey box, no reserved gap.
export const UncoveredMap: Story = {
  name: 'Empty — uncovered map (thumbnailUrl undefined, not a defect)',
  args: { mapName: 'Some Custom Scenario' },
}

// §4 "error" — the URL resolved but the image fails to load/decode. Must be pixel-identical to
// UncoveredMap above: the image and its frame are removed together, never an empty frame.
export const FailedImage: Story = {
  name: 'Error — image fails to load (must render identically to the empty story above)',
  args: { thumbnailUrl: '/game-assets/maps/does-not-exist.webp', mapName: 'Some Custom Scenario' },
}

// §4 "empty" (second case) — `mapName` is `null`: the source recorded no map name at all, a
// different and rarer fact than "the pack does not cover this name". No thumbnail is ever guessed.
export const NoMapNameAtAll: Story = {
  name: 'Empty — no map name at all (null, UnresolvedIdentifier treatment)',
  args: { thumbnailUrl: ARABIA_URL, mapName: null },
}

// §4 "loading" — caller-rendered Skeleton pair at the frame's exact footprint.
export const Loading: Story = {
  name: 'Loading (caller-rendered Skeleton pair, not a state of this component)',
  render: () => (
    <div className="flex items-center gap-3">
      <Skeleton variant="block" className="h-16 w-16 rounded-control" />
      <Skeleton variant="text" className="w-24" />
    </div>
  ),
}

// The 1280 table story: a row with a thumbnail and a row without one, at the same size, showing
// the row height is unaffected by whether the map is covered (§9 acceptance).
export const TableRowsSameHeight: Story = {
  name: '1280 table — covered and uncovered rows at the same height',
  render: () => (
    <table className="border-collapse">
      <tbody>
        <tr className="border-b border-border">
          <td className="p-3">
            <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="sm" />
          </td>
        </tr>
        <tr className="border-b border-border">
          <td className="p-3">
            <MapThumbnail mapName="Some Custom Scenario" size="sm" />
          </td>
        </tr>
      </tbody>
    </table>
  ),
}

export const CombinedList: Story = {
  name: 'Combined — covered, uncovered, failed and no-name side by side',
  render: () => (
    <ul className="flex flex-col gap-4">
      <li>
        <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" />
      </li>
      <li>
        <MapThumbnail mapName="Some Custom Scenario" />
      </li>
      <li>
        <MapThumbnail
          thumbnailUrl="/game-assets/maps/does-not-exist.webp"
          mapName="Some Custom Scenario"
        />
      </li>
      <li>
        <MapThumbnail thumbnailUrl={ARABIA_URL} mapName={null} />
      </li>
    </ul>
  ),
}
