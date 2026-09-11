import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { Skeleton } from '../../primitives/Skeleton'
import { CivilisationIcon } from './index'

const meta: Meta<typeof CivilisationIcon> = {
  id: 'composite-civilisationicon',
  title: 'Composites/Match & game data/CivilisationIcon',
  component: CivilisationIcon,
  parameters: {
    docs: {
      description: {
        component: `Lets a reader tell which civilisation a player played at a glance, from the game's own mark shown beside the civilisation's name.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof CivilisationIcon>

const BRITONS_URL = '/game-assets/civilisations/britons.webp'

export const Default: Story = {
  args: { iconUrl: BRITONS_URL, name: 'Britons' },
}

export const SizeMd: Story = {
  name: 'Size — md (default, MatchRow)',
  args: { iconUrl: BRITONS_URL, name: 'Britons', size: 'md' },
}

export const SizeLg: Story = {
  name: 'Size — lg (MatchDetailPanel)',
  args: { iconUrl: BRITONS_URL, name: 'Britons', size: 'lg' },
}

export const BothSizes: Story = {
  name: 'Both sizes in one frame',
  render: () => (
    <div className="flex items-center gap-6">
      <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" size="md" />
      <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" size="lg" />
    </div>
  ),
}

// §4 "empty" — a known name outside the shipped pack: `civilisationIcon()` returned `undefined`.
// This is the designed degrade path (FR-010), not a defect — no box, no silhouette, no dimming.
export const UncoveredCivilisation: Story = {
  name: 'Empty — uncovered civilisation (iconUrl undefined, not a defect)',
  args: { name: 'Gurjaras' },
}

// §4 "error" — `iconUrl` resolved but the request 404s / fails to decode. Must be pixel-identical
// to UncoveredCivilisation above: the onError handler removes the mark entirely, never a broken
// image glyph.
export const FailedImage: Story = {
  name: 'Error — image fails to load (must render identically to the empty story above)',
  args: { iconUrl: '/game-assets/civilisations/does-not-exist.webp', name: 'Gurjaras' },
}

// §4 "empty" (second case) — the API's own contract guarantee (`civ_name` present whenever
// `civ_id` is) is violated: no name at all, so the mark is suppressed and the literal wording
// `format.ts` already uses elsewhere is shown, never a fresh phrase for the same gap.
export const BlankName: Story = {
  name: 'Empty — no name at all (contract violation upstream, still renders safely)',
  args: { iconUrl: BRITONS_URL, name: undefined },
}

// §4 "loading" — the caller renders a Skeleton pair at the mark's exact footprint; this component
// has no loading state of its own. `Skeleton` stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  name: 'Loading (caller-rendered Skeleton pair, not a state of this component)',
  render: () => (
    <div className="flex items-center gap-2">
      <Skeleton variant="block" className="h-6 w-6 rounded-control" />
      <Skeleton variant="text" className="w-20" />
    </div>
  ),
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

// Acceptance: every story renders a name, the uncovered and failed stories overlay pixel-for-pixel,
// and greyscale still identifies the civilisation by name alone.
export const CombinedRow: Story = {
  name: 'Combined — covered, uncovered and failed side by side',
  render: () => (
    <ul className="flex flex-col gap-3">
      <li>
        <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />
      </li>
      <li>
        <CivilisationIcon name="Gurjaras" />
      </li>
      <li>
        <CivilisationIcon
          iconUrl="/game-assets/civilisations/does-not-exist.webp"
          name="Gurjaras"
        />
      </li>
    </ul>
  ),
}

// civilisation-icon.md §4 "hover / focus-visible / active — none... disabled — never." All four
// grouped: the enclosing row link owns interaction, this mark never does.
export const HoverFocusActiveDisabledNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        This mark has no hover, focus, active or disabled rendering of its own — it is a fact, not a
        control. The enclosing row's own link owns the hover fill.
      </p>
      <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />
    </div>
  ),
}
