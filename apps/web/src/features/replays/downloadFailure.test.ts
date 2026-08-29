import { describe, expect, it } from 'vitest'
import { parseReplayDownloadFailure, searchWithoutReplayDownloadFailure } from './downloadFailure'

describe('parseReplayDownloadFailure', () => {
  it('returns null for an ordinary visit with no query string at all', () => {
    expect(parseReplayDownloadFailure('')).toBeNull()
  })

  it('returns null when replay_error is present without a profile id to attach it to', () => {
    expect(parseReplayDownloadFailure('?replay_error=expired')).toBeNull()
  })

  it('returns null for a query string carrying only an unrelated parameter', () => {
    expect(parseReplayDownloadFailure('?link=1')).toBeNull()
  })

  it('parses the boundary-race code and its profile id, with no retry_after', () => {
    const failure = parseReplayDownloadFailure(
      '?replay_error=expired_since_page_load&replay_error_profile_id=196240',
    )
    expect(failure).toEqual({
      code: 'expired_since_page_load',
      profileId: '196240',
      retryAfterSeconds: undefined,
    })
  })

  it('parses rate_limited with its exact retry_after, never rounded or invented', () => {
    const failure = parseReplayDownloadFailure(
      '?replay_error=rate_limited&replay_error_profile_id=196240&replay_error_retry_after=42',
    )
    expect(failure).toEqual({
      code: 'rate_limited',
      profileId: '196240',
      retryAfterSeconds: 42,
    })
  })

  it('ignores a non-numeric retry_after rather than propagating a broken value', () => {
    const failure = parseReplayDownloadFailure(
      '?replay_error=rate_limited&replay_error_profile_id=196240&replay_error_retry_after=soon',
    )
    expect(failure?.retryAfterSeconds).toBeUndefined()
  })

  it('parses a generic failure code (never_recorded, expired, not_found) the same way', () => {
    const failure = parseReplayDownloadFailure(
      '?replay_error=never_recorded&replay_error_profile_id=11',
    )
    expect(failure).toEqual({
      code: 'never_recorded',
      profileId: '11',
      retryAfterSeconds: undefined,
    })
  })

  // L15 remediation (2026-08-29): `replay_error` is read straight off the URL, unauthenticated —
  // a caller can type any string. Only the fixed set `download_replay_point_of_view`
  // (`apps/api/.../routers/replays.py`) can actually raise through this redirect may drive an
  // alert on the page; anything else is ignored exactly like an ordinary visit.

  it('ignores a code outside the fixed set this route can actually raise', () => {
    expect(
      parseReplayDownloadFailure('?replay_error=totally_bogus&replay_error_profile_id=11'),
    ).toBeNull()
  })

  it('ignores a code from a different feature’s error-code table (contracts/http-api.md)', () => {
    expect(
      parseReplayDownloadFailure('?replay_error=sign_in_required&replay_error_profile_id=11'),
    ).toBeNull()
  })

  // 2026-08-29 remediation: a source 5xx, a timeout, or any other non-200/404 `aoe.ms` response
  // now reaches `_match_page_redirect_for_download_failure` as `source_unavailable` (translated
  // from `ProviderUnavailable`, `apps/api/.../routers/replays.py`) rather than escaping to the
  // generic 500 handler — this route's own allow-list has to widen to admit it.

  it('accepts source_unavailable — a source outage, not evidence the recording never existed', () => {
    const failure = parseReplayDownloadFailure(
      '?replay_error=source_unavailable&replay_error_profile_id=11',
    )
    expect(failure).toEqual({
      code: 'source_unavailable',
      profileId: '11',
      retryAfterSeconds: undefined,
    })
  })

  // The allow-list widens deliberately, one exact string at a time — it must not have loosened
  // into accepting anything that merely looks like a real code.

  it('still rejects a code that only resembles source_unavailable', () => {
    expect(
      parseReplayDownloadFailure('?replay_error=source_unreachable&replay_error_profile_id=11'),
    ).toBeNull()
  })
})

describe('searchWithoutReplayDownloadFailure', () => {
  it('returns an empty string when the failure params were the only thing present', () => {
    expect(
      searchWithoutReplayDownloadFailure(
        '?replay_error=expired&replay_error_profile_id=11&replay_error_retry_after=5',
      ),
    ).toBe('')
  })

  it('strips only this module’s own three parameters, keeping every other one untouched', () => {
    expect(
      searchWithoutReplayDownloadFailure(
        '?tab=history&replay_error=expired&replay_error_profile_id=11',
      ),
    ).toBe('?tab=history')
  })

  it('returns an empty string for a query string that never carried a failure', () => {
    expect(searchWithoutReplayDownloadFailure('')).toBe('')
  })
})
