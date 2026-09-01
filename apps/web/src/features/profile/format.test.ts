import { describe, expect, it } from 'vitest'
import {
  formatCountryName,
  formatFreshness,
  formatObjectedAt,
  formatRank,
  formatRating,
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

describe('formatObjectedAt', () => {
  it('formats an ISO timestamp as "on <readable date>"', () => {
    const result = formatObjectedAt('2026-08-01T09:30:00Z')
    // Locale-dependent exact string (Intl.DateTimeFormat), so this asserts the year and the
    // leading "on" survive the round trip rather than pinning an exact rendering that would break
    // across CI timezones.
    expect(result).toMatch(/^on /)
    expect(result).toContain('2026')
  })
})

// `country-flag.md` §2a: `Intl.DisplayNames(['en'], { type: 'region' })`, locale fixed to `en`
// regardless of the runner's own locale (constitution XI, machine-independent baselines). Mirrors
// `features/players/format.test.ts`'s identical suite for its own, deliberately duplicated,
// `formatCountryName` (`format.ts`'s own note on why it is not shared).
describe('formatCountryName', () => {
  it('resolves a lowercase ISO alpha-2 code to its English display name', () => {
    expect(formatCountryName('fr')).toBe('France')
  })

  it('resolves an uppercase ISO alpha-2 code the same way', () => {
    expect(formatCountryName('FR')).toBe('France')
  })

  it('shows a value that is not a two-letter code verbatim, never a mangled lookup', () => {
    expect(formatCountryName('Germany')).toBe('Germany')
  })

  it('returns undefined for null', () => {
    expect(formatCountryName(null)).toBeUndefined()
  })

  it('returns undefined for undefined', () => {
    expect(formatCountryName(undefined)).toBeUndefined()
  })

  it('returns undefined for a blank string after trimming', () => {
    expect(formatCountryName('   ')).toBeUndefined()
  })
})
