import { describe, expect, it } from 'vitest'
import { isUploadEligible } from './uploadEligibility'

describe('isUploadEligible', () => {
  it.each(['unavailable', 'expired', 'failed'])(
    'is eligible for the "Lost" status %s',
    (status) => {
      expect(isUploadEligible(status)).toBe(true)
    },
  )

  it.each(['stored', 'pending', 'downloading', 'quarantined'])(
    'is not eligible for %s — DownloadAction, an in-flight capture, or a review-only row',
    (status) => {
      expect(isUploadEligible(status)).toBe(false)
    },
  )

  // T722: `withdrawn` is not one of the "Lost" statuses (capture-state-badge.md §3, "a fifth
  // state"). Withheld because the row may hold an object the upload would overwrite (constitution
  // IV, the reason `quarantined` is withheld), on that reason alone, pending T723. The allowlist
  // already excludes it; this pins why.
  it('is not eligible for withdrawn — the row may hold an object an upload would overwrite (IV)', () => {
    expect(isUploadEligible('withdrawn')).toBe(false)
  })

  it('is not eligible when no capture row exists yet', () => {
    expect(isUploadEligible(null)).toBe(false)
    expect(isUploadEligible(undefined)).toBe(false)
  })

  it('is not eligible for an unrecognised status', () => {
    expect(isUploadEligible('totally_bogus')).toBe(false)
  })
})
