import { describe, expect, it } from 'vitest'
import {
  formatFreshness,
  formatRank,
  formatRating,
  formatRecordedAt,
  formatStreak,
  formatWinRate,
} from './format'

describe('formatRating', () => {
  it('adds thousands separators the way en-US does', () => {
    expect(formatRating(1234)).toBe('1,234')
  })

  it('leaves a small number unchanged', () => {
    expect(formatRating(987)).toBe('987')
  })
})

describe('formatRank', () => {
  it('renders undefined for -1 (Relic convention: not enough games for a rank yet)', () => {
    expect(formatRank(-1)).toBeUndefined()
  })

  it('renders undefined for 0, never "0" or "rank 0"', () => {
    expect(formatRank(0)).toBeUndefined()
  })

  it('renders undefined for null', () => {
    expect(formatRank(null)).toBeUndefined()
  })

  it('renders a real, positive rank as a formatted string', () => {
    expect(formatRank(42)).toBe('42')
  })

  it('formats a large rank with thousands separators', () => {
    expect(formatRank(12345)).toBe('12,345')
  })
})

describe('formatWinRate', () => {
  it('is 0% when there are no games at all, never NaN or division by zero', () => {
    expect(formatWinRate(0, 0)).toBe('0%')
  })

  it('rounds to the nearest whole percent', () => {
    expect(formatWinRate(2, 1)).toBe('67%')
  })

  it('is 100% with only wins', () => {
    expect(formatWinRate(5, 0)).toBe('100%')
  })

  it('is 0% with only losses', () => {
    expect(formatWinRate(0, 5)).toBe('0%')
  })
})

describe('formatStreak', () => {
  it('renders undefined for null (no current streak)', () => {
    expect(formatStreak(null)).toBeUndefined()
  })

  it('renders undefined for undefined', () => {
    expect(formatStreak(undefined)).toBeUndefined()
  })

  it('renders undefined for zero, so it disappears rather than showing "W0"', () => {
    expect(formatStreak(0)).toBeUndefined()
  })

  it('renders a positive streak as a win streak', () => {
    expect(formatStreak(3)).toBe('W3')
  })

  it('renders a negative streak as a loss streak, using the absolute value', () => {
    expect(formatStreak(-4)).toBe('L4')
  })
})

describe('formatFreshness', () => {
  const now = new Date('2026-08-21T12:00:00Z').getTime()

  it('is undefined when nothing has ever been captured', () => {
    expect(formatFreshness(undefined, now)).toBeUndefined()
  })

  it('reports "just now" within a minute of now', () => {
    const result = formatFreshness(now - 10_000, now)
    expect(result).toMatch(/^Updated just now \(/)
  })

  it('reports minutes for a gap under an hour', () => {
    const result = formatFreshness(now - 5 * 60_000, now)
    expect(result).toMatch(/^Updated 5 minutes ago \(/)
  })

  it('reports hours for a gap under a day', () => {
    const result = formatFreshness(now - 3 * 60 * 60_000, now)
    expect(result).toMatch(/^Updated 3 hours ago \(/)
  })

  it('reports days for a gap of a day or more', () => {
    const result = formatFreshness(now - 2 * 24 * 60 * 60_000, now)
    expect(result).toMatch(/^Updated 2 days ago \(/)
  })
})

describe('formatRecordedAt', () => {
  it('formats an ISO timestamp as a readable date and time', () => {
    const result = formatRecordedAt('2026-08-01T09:30:00Z')
    // Locale-dependent exact string (Intl.DateTimeFormat), so this asserts the year and month
    // survive the round trip rather than pinning an exact rendering that would break across CI
    // timezones.
    expect(result).toContain('2026')
    expect(result.length).toBeGreaterThan(0)
  })
})
