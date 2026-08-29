import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ReplayAvailabilityRowData } from './index'
import { ReplayAvailabilityList } from './index'

const meta: Meta<typeof ReplayAvailabilityList> = {
  title: 'Composite/ReplayAvailabilityList',
  component: ReplayAvailabilityList,
}

export default meta
type Story = StoryObj<typeof ReplayAvailabilityList>

// Dates are computed relative to render time, not a fixed date, so the countdown text stays the
// same ("6 days left", "3 hours left", ...) no matter which day this story is captured — the same
// technique `CaptureStateBadge.stories.tsx` uses for its own deadlines.
const HOUR_MS = 60 * 60_000
const DAY_MS = 24 * HOUR_MS

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

export const Archived: Story = {
  args: {
    rows: [{ id: '1', alias: 'GL.TheViper', availability: 'archived' }],
  },
}

// The `obtainable` row with a seeded `obtainableUntil` shows a countdown in the correct unit —
// days here.
export const ObtainableWithCountdown: Story = {
  args: {
    rows: [
      {
        id: '1',
        alias: 'Hera',
        availability: 'obtainable',
        obtainableUntil: inFromNow(6 * DAY_MS),
      },
    ],
  },
}

// T340's own requirement: a story seeded a few hours from `obtainableUntil` shows the hours unit,
// not days rounded up and not minutes — same wording shape as
// `CaptureStateBadge.stories.tsx`'s `StillCatchableHours`.
export const ObtainableHoursFromBoundary: Story = {
  name: 'Obtainable — a few hours from the boundary',
  args: {
    rows: [
      {
        id: '1',
        alias: 'DauT',
        availability: 'obtainable',
        obtainableUntil: inFromNow(3 * HOUR_MS),
      },
    ],
  },
}

// §3.2, FR-024 amended 2026-08-29: `obtainableUntil: null` is an ordinary shape, not a degraded
// one — the badge and tone read identically to the dated story above, with no `SecondaryLine` and
// no invented date.
export const ObtainableNoDate: Story = {
  name: 'Obtainable — obtainable_until is null (retention window unresolved, FR-024)',
  args: {
    rows: [{ id: '1', alias: 'TaToH', availability: 'obtainable', obtainableUntil: null }],
  },
}

export const Expired: Story = {
  args: {
    rows: [{ id: '1', alias: 'Liereyy', availability: 'expired' }],
  },
}

// §5 "the boundary race": distinct SecondaryLine from the plain `Expired` story above, placed
// separately so the two are never confused with one another.
export const ExpiredSincePageLoad: Story = {
  name: 'Expired — the boundary race (was obtainable when the page loaded)',
  args: {
    rows: [{ id: '1', alias: 'MbL', availability: 'expired', expiredSincePageLoad: true }],
  },
}

export const NeverRecorded: Story = {
  args: {
    rows: [{ id: '1', alias: 'Yo', availability: 'never_recorded' }],
  },
}

// §11 acceptance: all four states in one frame, each identifiable by label text alone — no two
// sharing a label — and `expired`/`never_recorded` distinct from each other by tone as well
// (`danger` vs `neutral`), the same as `archived`/`obtainable` (`success` vs `info`).
export const AllFourStates: Story = {
  args: {
    rows: [
      { id: '1', alias: 'GL.TheViper', availability: 'archived' },
      {
        id: '2',
        alias: 'Hera',
        availability: 'obtainable',
        obtainableUntil: inFromNow(6 * DAY_MS),
      },
      { id: '3', alias: 'Liereyy', availability: 'expired' },
      { id: '4', alias: 'Yo', availability: 'never_recorded' },
    ],
  },
}

// §11: the dated and `null`-dated `obtainable` rows in the same frame — the only difference is
// the countdown's presence, nothing else about the badge or tone.
export const ObtainableDatedAndUndated: Story = {
  name: 'Obtainable — dated and undated obtainable_until, side by side',
  args: {
    rows: [
      {
        id: '1',
        alias: 'Hera',
        availability: 'obtainable',
        obtainableUntil: inFromNow(6 * DAY_MS),
      },
      { id: '2', alias: 'TaToH', availability: 'obtainable', obtainableUntil: null },
    ],
  },
}

// §5 "empty": a match old enough (or unlucky enough) that nothing is obtainable from anyone still
// shows the section heading and one row per participant — never a single collapsed message.
export const EveryRowUnobtainable: Story = {
  name: 'Every row expired/never_recorded — still one row each, never collapsed',
  args: {
    rows: [
      { id: '1', alias: 'Liereyy', availability: 'expired' },
      { id: '2', alias: 'MbL', availability: 'expired' },
      { id: '3', alias: 'Yo', availability: 'never_recorded' },
      { id: '4', alias: 'F1Re', availability: 'never_recorded' },
    ],
  },
}

// §5 "loading": before the match detail response arrives — skeleton row count (2) matches the
// smallest known participant count, at the row's own footprint.
export const Loading: Story = {
  args: { loading: true },
}

// §5 "error" — request could not be started at all: the row returns to default (button still
// present and pressable) with a danger `Callout` beneath it — never a row that looks like it gave
// up.
export const DownloadStartFailed: Story = {
  args: {
    rows: [
      {
        id: '1',
        alias: 'Hera',
        availability: 'obtainable',
        obtainableUntil: inFromNow(6 * DAY_MS),
        downloadState: 'error',
      },
    ],
  },
}

// §5 "error" — FR-028's rate limit: the exact `retry_after` seconds the response carried, never
// rounded or invented.
export const RateLimited: Story = {
  args: {
    rows: [
      {
        id: '1',
        alias: 'GL.TheViper',
        availability: 'archived',
        downloadState: 'rate_limited',
        retryAfterSeconds: 42,
      },
    ],
  },
}

// `DownloadAction`'s own `loading` state — "Preparing your download…" — while the signed URL or
// stream is being requested.
export const DownloadPreparing: Story = {
  args: {
    rows: [
      {
        id: '1',
        alias: 'GL.TheViper',
        availability: 'archived',
        downloadState: 'loading',
      },
    ],
  },
}

// A realistic combined story: one match's full roster, mixing every availability and one row
// currently rate limited — the shape `apps/web`'s match detail page (T341) actually renders.
const realisticRows: ReplayAvailabilityRowData[] = [
  { id: '1', alias: 'GL.TheViper', availability: 'archived' },
  {
    id: '2',
    alias: 'Hera',
    availability: 'obtainable',
    obtainableUntil: inFromNow(2 * DAY_MS),
  },
  {
    id: '3',
    alias: 'DauT',
    availability: 'obtainable',
    downloadState: 'rate_limited',
    retryAfterSeconds: 17,
  },
  { id: '4', alias: 'Liereyy', availability: 'expired' },
  { id: '5', alias: 'Yo', availability: 'never_recorded' },
]

export const RealisticMatch: Story = {
  args: { rows: realisticRows },
}
