import { describe, expect, it } from 'vitest'
import { isUploadEligible } from './uploadEligibility'

describe('isUploadEligible', () => {
  it.each(['unavailable', 'expired', 'failed'])(
    'is eligible for the "Lost" status %s',
    (status) => {
      expect(isUploadEligible(status, null)).toBe(true)
    },
  )

  it.each(['stored', 'pending', 'downloading', 'quarantined'])(
    'is not eligible for %s — DownloadAction, an in-flight capture, or a review-only row',
    (status) => {
      expect(isUploadEligible(status, null)).toBe(false)
    },
  )

  // T722/T727: `withdrawn` is not one of the "Lost" statuses (capture-state-badge.md §3, "a fifth
  // state"). It is offered only where the match says the row names no object.
  it('is eligible for withdrawn when the row holds no object (capture_object_held false)', () => {
    expect(isUploadEligible('withdrawn', false)).toBe(true)
  })

  it('is not eligible for withdrawn when the row holds an object', () => {
    expect(isUploadEligible('withdrawn', true)).toBe(false)
  })

  it.each([null, undefined])(
    'is not eligible for withdrawn when capture_object_held is %s — only false says nothing is held',
    (held) => {
      expect(isUploadEligible('withdrawn', held)).toBe(false)
    },
  )

  it.each(['unavailable', 'expired', 'failed'])(
    'is eligible for %s whatever capture_object_held says',
    (status) => {
      expect(isUploadEligible(status, true)).toBe(true)
      expect(isUploadEligible(status, false)).toBe(true)
      expect(isUploadEligible(status, undefined)).toBe(true)
    },
  )

  it.each(['stored', 'pending', 'downloading', 'quarantined'])(
    'is not eligible for %s even when capture_object_held is false',
    (status) => {
      expect(isUploadEligible(status, false)).toBe(false)
    },
  )

  it('is not eligible when no capture row exists yet', () => {
    expect(isUploadEligible(null, false)).toBe(false)
    expect(isUploadEligible(undefined, false)).toBe(false)
  })

  it('is not eligible for an unrecognised status', () => {
    expect(isUploadEligible('totally_bogus', false)).toBe(false)
  })
})
