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

  it('is not eligible when no capture row exists yet', () => {
    expect(isUploadEligible(null)).toBe(false)
    expect(isUploadEligible(undefined)).toBe(false)
  })

  it('is not eligible for an unrecognised status', () => {
    expect(isUploadEligible('totally_bogus')).toBe(false)
  })
})
