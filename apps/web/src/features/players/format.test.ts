import { describe, expect, it } from 'vitest'
import { formatAliasObservedAt } from './format'

describe('formatAliasObservedAt', () => {
  it('formats an ISO timestamp as a readable date', () => {
    const result = formatAliasObservedAt('2026-08-12T00:00:00Z')
    // Locale-dependent exact string (Intl.DateTimeFormat), so this asserts the year survives the
    // round trip rather than pinning an exact rendering that would break across CI timezones
    // (mirrors `features/profile/format.test.ts`'s identical rule for `formatRecordedAt`).
    expect(result).toContain('2026')
    expect(result.length).toBeGreaterThan(0)
  })
})
