import { describe, expect, it } from 'vitest'
import type { ApiMatchParticipant } from '../matches/api'
import { toReplayAvailabilityRows } from './availability'

function participant(overrides: Partial<ApiMatchParticipant> = {}): ApiMatchParticipant {
  return {
    profile_id: 2,
    alias: 'Rival',
    team_id: 2,
    civ_id: 3,
    civ_name: 'Celts',
    color_id: 2,
    result: 'loss',
    rating: 1500,
    rating_diff: -12,
    replay: {
      profile_id: 2,
      availability: 'obtainable',
      obtainable_until: null,
      download_path: '/api/matches/700800900/replay/2',
    },
    ...overrides,
  }
}

describe('toReplayAvailabilityRows', () => {
  it('carries every participant, none dropped or duplicated', () => {
    const rows = toReplayAvailabilityRows([
      participant({ profile_id: 1, team_id: 1 }),
      participant({ profile_id: 2, team_id: 2 }),
    ])
    expect(rows.map((row) => row.id)).toEqual(['1', '2'])
  })

  it('orders rows the same way ParticipantsTable groups them — by team, in first-seen order', () => {
    const rows = toReplayAvailabilityRows([
      participant({ profile_id: 1, team_id: 2 }),
      participant({ profile_id: 2, team_id: 1 }),
      participant({ profile_id: 3, team_id: 2 }),
    ])
    // team 2 seen first, so its members lead, in the order they themselves appeared
    expect(rows.map((row) => row.id)).toEqual(['1', '3', '2'])
  })

  it('falls back to "Unknown player" for a null alias, matching toParticipantData', () => {
    const rows = toReplayAvailabilityRows([participant({ alias: null })])
    expect(rows[0]?.alias).toBe('Unknown player')
  })

  it('carries availability and obtainable_until straight off the wire, per participant', () => {
    const rows = toReplayAvailabilityRows([
      participant({
        profile_id: 5,
        replay: {
          profile_id: 5,
          availability: 'archived',
          obtainable_until: null,
          download_path: '/api/matches/1/replay/5',
        },
      }),
    ])
    expect(rows[0]?.availability).toBe('archived')
    expect(rows[0]?.obtainableUntil).toBeNull()
  })

  it('never invents an obtainable_until date while the retention window is unresolved (FR-024)', () => {
    const rows = toReplayAvailabilityRows([
      participant({
        replay: {
          profile_id: 2,
          availability: 'obtainable',
          obtainable_until: null,
          download_path: '/api/matches/700800900/replay/2',
        },
      }),
    ])
    expect(rows[0]?.obtainableUntil).toBeNull()
  })

  it('defaults every row to the idle download state when none is supplied', () => {
    const rows = toReplayAvailabilityRows([participant({ profile_id: 1 })])
    expect(rows[0]?.downloadState).toBe('idle')
  })

  it('looks up each row’s own download state by id, never mixing rows up', () => {
    const rows = toReplayAvailabilityRows(
      [participant({ profile_id: 1 }), participant({ profile_id: 2 })],
      { '1': 'loading' },
    )
    expect(rows.find((row) => row.id === '1')?.downloadState).toBe('loading')
    expect(rows.find((row) => row.id === '2')?.downloadState).toBe('idle')
  })

  it('maps an empty participant list to an empty row list', () => {
    expect(toReplayAvailabilityRows([])).toEqual([])
  })

  // 2026-08-29 remediation: the redirect-carried `failure` overrides exactly one row — the one
  // `failure.profileId` names — never any other, and never when absent.

  it('renders the boundary race as an in-place transition to expired, not a Callout', () => {
    const rows = toReplayAvailabilityRows(
      [
        participant({
          profile_id: 1,
          replay: {
            profile_id: 1,
            // The freshly-fetched availability is already never_recorded (`derive_availability`'s
            // own `recorded_404` reading) by the time this page reloads — the override below is
            // what still shows the boundary-race sentence for this one render.
            availability: 'never_recorded',
            obtainable_until: null,
            download_path: null,
          },
        }),
      ],
      {},
      { code: 'expired_since_page_load', profileId: '1' },
    )
    expect(rows[0]?.availability).toBe('expired')
    expect(rows[0]?.expiredSincePageLoad).toBe(true)
    expect(rows[0]?.downloadState).toBe('idle')
  })

  it('renders rate_limited with the exact retry_after the redirect carried', () => {
    const rows = toReplayAvailabilityRows(
      [participant({ profile_id: 1 })],
      {},
      { code: 'rate_limited', profileId: '1', retryAfterSeconds: 42 },
    )
    expect(rows[0]?.downloadState).toBe('rate_limited')
    expect(rows[0]?.retryAfterSeconds).toBe(42)
  })

  it('renders any other failure code as the generic could-not-start-download error', () => {
    const rows = toReplayAvailabilityRows(
      [participant({ profile_id: 1 })],
      {},
      { code: 'never_recorded', profileId: '1' },
    )
    expect(rows[0]?.downloadState).toBe('error')
    expect(rows[0]?.availability).toBe('obtainable')
  })

  // M9 remediation (2026-08-29): `_source_rate_limited_error` (`apps/api/.../routers/replays.py`)
  // raises the identical `rate_limited` code with no `retry_after` at all — `ReplayAvailabilityList`
  // documents `retryAfterSeconds` as required once `downloadState === 'rate_limited'`, so this
  // mapping must not enter that state without the figure it documents, rather than relying on the
  // component's own null-check to silently choose the generic wording instead.

  it('falls back to the generic error, not rate_limited, when the redirect carried no retry_after', () => {
    const rows = toReplayAvailabilityRows(
      [participant({ profile_id: 1 })],
      {},
      { code: 'rate_limited', profileId: '1', retryAfterSeconds: undefined },
    )
    expect(rows[0]?.downloadState).toBe('error')
    expect(rows[0]?.retryAfterSeconds).toBeUndefined()
  })

  it('never applies the failure to a row it does not name', () => {
    const rows = toReplayAvailabilityRows(
      [participant({ profile_id: 1 }), participant({ profile_id: 2 })],
      {},
      { code: 'never_recorded', profileId: '1' },
    )
    expect(rows.find((row) => row.id === '2')?.downloadState).toBe('idle')
  })

  it('leaves every row untouched when no failure was carried', () => {
    const rows = toReplayAvailabilityRows([participant({ profile_id: 1 })], {}, null)
    expect(rows[0]?.downloadState).toBe('idle')
    expect(rows[0]?.expiredSincePageLoad).toBeUndefined()
  })
})
