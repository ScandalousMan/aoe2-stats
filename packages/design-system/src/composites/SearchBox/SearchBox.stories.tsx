import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import type { PlayerSearchResultData } from '../PlayerResultRow'
import { SearchBox } from './index'
import type { SearchBoxState } from './index'

const meta: Meta<typeof SearchBox> = {
  title: 'Composite/SearchBox',
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

export const Loading: Story = {
  name: 'loading — a query is in flight (skeleton footprint matches the loaded rows)',
  render: () => <DemoSearchBox state={{ status: 'loading' }} />,
}

export const Found: Story = {
  name: 'default — found, most-played first, no DegradedBanner',
  render: () => (
    <DemoSearchBox state={{ status: 'answered', query: 'viper', results, degraded: false }} />
  ),
}

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
  name: 'empty 2 of 3 — search degraded, fallback found nothing either (one Callout, not two)',
  render: () => (
    <DemoSearchBox
      initialValue="xyzzy"
      state={{ status: 'answered', query: 'xyzzy', results: [], degraded: true }}
    />
  ),
}

export const RateLimited: Story = {
  name: 'error — rate limited (Callout/warning, Input disabled, countdown sentence in the same frame)',
  render: () => <DemoSearchBox state={{ status: 'rate-limited', retryAfterSeconds: 8 }} />,
}

export const RequestFailed: Story = {
  name: 'error — request failed (Callout/danger, distinct from a degraded-but-successful response)',
  render: () => <DemoSearchBox state={{ status: 'failed' }} />,
}
