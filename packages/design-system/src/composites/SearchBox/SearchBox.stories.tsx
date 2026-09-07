import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import type { PlayerSearchResultData } from '../PlayerResultRow'
import { SearchBox } from './index'
import type { SearchBoxState } from './index'

const meta: Meta<typeof SearchBox> = {
  id: 'composite-searchbox',
  title: 'Composites/Search & favourites/SearchBox',
  component: SearchBox,
}

export default meta
type Story = StoryObj<typeof SearchBox>

const results: PlayerSearchResultData[] = [
  {
    profileId: '1',
    href: '/players/1',
    alias: 'TheViper',
    country: 'Netherlands',
    gamesPlayed: 8213,
    clan: null,
  },
  {
    profileId: '2',
    href: '/players/2',
    alias: 'TheViper',
    country: 'Belgium',
    gamesPlayed: 412,
    clan: 'RED',
  },
  {
    profileId: '3',
    href: '/players/3',
    alias: 'Hera',
    country: 'Israel',
    gamesPlayed: 5120,
    clan: 'GL',
  },
]

// `state` demonstrates one fixed named state per story (§5); `value`/`onValueChange` stay locally
// managed so the input remains interactive in the doc, matching the caller/presenter split T322
// draws between fetching (the route) and rendering (this component).
function DemoSearchBox({
  state,
  initialValue = 'viper',
}: {
  state: SearchBoxState
  initialValue?: string
}) {
  const [value, setValue] = useState(initialValue)
  return (
    <div className="max-w-xl">
      <SearchBox
        value={value}
        onValueChange={setValue}
        onSearch={() => {}}
        state={state}
        onRetry={() => {}}
      />
    </div>
  )
}

export const Idle: Story = {
  name: 'default — no query has been submitted yet (plain text, not a Callout)',
  render: () => <DemoSearchBox initialValue="" state={{ status: 'idle' }} />,
}

// `status: 'loading'` renders `Skeleton` rows, which stay invisible for the first
// `duration.normal` (200ms, `useDelayedVisible`) so a fast-resolving query never flashes a pulse —
// a `setTimeout`, not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the
// pulse to exist, rather than screenshotting whatever frame Storybook happened to reach first, is
// what makes this baseline the same no matter how long mounting this particular story took.
export const Loading: Story = {
  name: 'loading — a query is in flight (skeleton footprint matches the loaded rows)',
  render: () => <DemoSearchBox state={{ status: 'loading' }} />,
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

export const Found: Story = {
  name: 'default — found, most-played first, no DegradedBanner',
  render: () => (
    <DemoSearchBox state={{ status: 'answered', query: 'viper', results, degraded: false }} />
  ),
}

// The "N of 3" numbering below is a display name only — it does not touch the export names above,
// which is what a baseline filename is keyed on (`story-baselines.mjs`'s own header comment), so
// renumbering here orphans nothing. T572 scenario 9 found `DegradedAndEmpty` still reading "2 of 3",
// the same number as `DegradedWithResults` immediately above it, and no story reading "3 of 3" at
// all — fixed below.
export const NotFound: Story = {
  name: 'empty 1 of 3 — found nothing (Callout/info, distinguishable from degraded by tone and copy)',
  render: () => (
    <DemoSearchBox
      initialValue="xyzzy"
      state={{ status: 'answered', query: 'xyzzy', results: [], degraded: false }}
    />
  ),
}

export const DegradedWithResults: Story = {
  name: 'empty 2 of 3 — search degraded, fallback found rows (banner and rows in the same frame)',
  render: () => (
    <DemoSearchBox
      state={{ status: 'answered', query: 'viper', results: results.slice(0, 1), degraded: true }}
    />
  ),
}

export const DegradedAndEmpty: Story = {
  name: 'empty 3 of 3 — search degraded, fallback found nothing either (one Callout, not two)',
  render: () => (
    <DemoSearchBox
      initialValue="xyzzy"
      state={{ status: 'answered', query: 'xyzzy', results: [], degraded: true }}
    />
  ),
}

// The rate-limited countdown sentence ("Try again in Ns.") depends on real elapsed time since
// mount: `SearchBox` decrements `secondsLeft` once per real `window.setInterval` tick (index.tsx),
// rather than reading a wall clock — freezing `Date.now` (`CaptureStateBadge.stories.tsx`'s own
// technique for its live clock) would do nothing here, because the decrement counts ticks fired,
// not time elapsed. T550 measured exactly this: the same commit's `RateLimited` baseline read
// "Try again in 7s." from one CI capture and "Try again in 6s." from the next, purely because the
// screenshot fired a beat later relative to mount and caught one extra tick — invisible to the
// visual gate (0.095% of pixels, under `maxDiffPixelRatio: 0.01`), so it silently rewrote its own
// baseline instead of ever failing (T568). `window.setInterval` is disabled here, in this story's
// own `beforeEach`, before `SearchBox` ever mounts, and restored by the returned cleanup once the
// story is torn down — never at module scope, which would leave every other `setInterval` consumer
// in the browsable Storybook preview (e.g. `CaptureStateBadge`, `ReplayAvailabilityList`) dead for
// the rest of the session (the defect this scoping fixes). `secondsLeft` stays at the value passed
// in (`state.retryAfterSeconds`) for as long as this story is on screen, so the sentence it exists
// to show ("You're searching too quickly. Try again in 8s.") stays exactly that sentence,
// deterministically, no matter when the screenshot fires.
export const RateLimited: Story = {
  name: 'error — rate limited (Callout/warning, Input disabled, countdown sentence in the same frame)',
  beforeEach: () => {
    const realSetInterval = window.setInterval
    window.setInterval = (() => 0) as unknown as typeof window.setInterval
    return () => {
      window.setInterval = realSetInterval
    }
  },
  render: () => <DemoSearchBox state={{ status: 'rate-limited', retryAfterSeconds: 8 }} />,
}

export const RequestFailed: Story = {
  name: 'error — request failed (Callout/danger, distinct from a degraded-but-successful response)',
  render: () => <DemoSearchBox state={{ status: 'failed' }} />,
}

// player-search.md §5 "hover / focus-visible / active — `Input`: standard text-input interaction,
// focus ring per DS-4."
export const Hover: Story = {
  render: () => <DemoSearchBox initialValue="" state={{ status: 'idle' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.hover(canvas.getByRole('textbox'))
  },
}

export const FocusVisible: Story = {
  render: () => <DemoSearchBox initialValue="" state={{ status: 'idle' }} />,
  play: async () => {
    await userEvent.tab()
  },
}
