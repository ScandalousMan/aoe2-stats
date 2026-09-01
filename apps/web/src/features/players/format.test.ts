import { describe, expect, it } from 'vitest'
import { formatAliasObservedAt, formatCountryName } from './format'

describe('formatAliasObservedAt', () => {
  it('formats an ISO timestamp as a readable date', () => {
    const result = formatAliasObservedAt('2026-08-12T00:00:00Z')
    // Locale-dependent exact string (Intl.DateTimeFormat), so this asserts the year survives the
    // round trip rather than pinning an exact rendering that would break across CI timezones
    // (mirrors `features/profile/format.test.ts`'s identical rule for `formatObjectedAt`).
    expect(result).toContain('2026')
    expect(result.length).toBeGreaterThan(0)
  })
})

// `country-flag.md` §2a: `Intl.DisplayNames(['en'], { type: 'region' })`, locale fixed to `en`
// regardless of the runner's own locale (constitution XI, machine-independent baselines).
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
