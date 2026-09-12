import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { Skeleton } from '../../primitives/Skeleton'
import { MapThumbnail } from './index'

const meta: Meta<typeof MapThumbnail> = {
  id: 'composite-mapthumbnail',
  title: 'Composites/Match & game data/MapThumbnail',
  component: MapThumbnail,
  parameters: {
    docs: {
      description: {
        component: `Shows which map a match was played on, as the minimap a player recognises instantly, beside the map's name.`,
      },
    },
  },
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

// visual-equivalence: composite-mapthumbnail--default: size 'md' is this component's own default
// (index.tsx's `size = 'md'`), so this renders identically to Default above.
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
// visual-equivalence: composite-mapthumbnail--uncovered-map: map-thumbnail.md §4 "error" requires
// this pixel-identical to UncoveredMap — the image and its frame are removed together.
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

// §4 "loading" — caller-rendered Skeleton pair at the frame's exact footprint. `Skeleton` stays
// invisible for the first `duration.normal` (200ms, `useDelayedVisible`) so a fast-resolving load
// never flashes a pulse — a `setTimeout`, not a wall clock, but a clock all the same (T568,
// FR-047). Waiting here for the pulse to exist, rather than screenshotting whatever frame
// Storybook happened to reach first, is what makes this baseline the same no matter how long
// mounting this particular story took.
export const Loading: Story = {
  name: 'Loading (caller-rendered Skeleton pair, not a state of this component)',
  render: () => (
    <div className="flex items-center gap-3">
      <Skeleton variant="block" className="h-16 w-16 rounded-control" />
      <Skeleton variant="text" className="w-24" />
    </div>
  ),
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
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

// map-thumbnail.md §4 "hover / focus-visible / active — none... disabled — never." All four
// grouped: the enclosing row link owns interaction, this mark never does.
export const HoverFocusActiveDisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        This thumbnail has no hover, focus, active or disabled rendering of its own — it is a fact
        about a finished match, not a control. The enclosing row's own link owns the hover fill.
      </p>
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" />
    </div>
  ),
}
