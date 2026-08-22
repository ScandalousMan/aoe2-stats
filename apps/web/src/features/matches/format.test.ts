import { describe, expect, it } from 'vitest'
import {
  formatCivilisation,
  formatDuration,
  formatLeaderboardName,
  formatOutcome,
  formatPlayedAtAbsolute,
  formatPlayedAtRelative,
} from './format'

describe('formatPlayedAtRelative', () => {
  const now = new Date('2026-08-22T12:00:00Z').getTime()

  it('reads "just now" for anything under a minute', () => {
    expect(formatPlayedAtRelative('2026-08-22T11:59:45Z', now)).toBe('just now')
  })

  it('reads in minutes under an hour', () => {
    expect(formatPlayedAtRelative('2026-08-22T11:45:00Z', now)).toBe('15 minutes ago')
  })

  it('reads in hours under a day', () => {
    expect(formatPlayedAtRelative('2026-08-22T09:00:00Z', now)).toBe('3 hours ago')
  })

  it('reads in days beyond that', () => {
    expect(formatPlayedAtRelative('2026-08-19T12:00:00Z', now)).toBe('3 days ago')
  })
})

describe('formatPlayedAtAbsolute', () => {
  it('formats a real date/time, not the raw ISO string', () => {
    const result = formatPlayedAtAbsolute('2026-08-22T11:45:00Z')
    expect(result).not.toContain('T')
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('formatDuration', () => {
  it('rounds seconds to the nearest minute label', () => {
    expect(formatDuration(2040)).toBe('34 min')
  })

  it('rounds up at the half-minute boundary', () => {
    expect(formatDuration(90)).toBe('2 min')
  })

  it('never shows raw seconds for a null duration', () => {
    expect(formatDuration(null)).toBe('Unknown duration')
  })
})

describe('formatOutcome', () => {
  it('passes "win" through', () => {
    expect(formatOutcome('win')).toBe('win')
  })

  it('passes "loss" through', () => {
    expect(formatOutcome('loss')).toBe('loss')
  })

  it('falls back to "loss" for anything unrecognised, never letting it reach the component', () => {
    expect(formatOutcome('draw')).toBe('loss')
    expect(formatOutcome(null)).toBe('loss')
  })
})

describe('formatCivilisation', () => {
  it('passes the server-named civilisation through unmodified (T070c)', () => {
    expect(formatCivilisation('Turks')).toBe('Turks')
  })

  it('reads as unknown for a null civilisation name', () => {
    expect(formatCivilisation(null)).toBe('Unknown civilisation')
  })
})

describe('formatLeaderboardName', () => {
  it('is a stand-in for a name the API does not send yet (T076), never a duplicated id table', () => {
    expect(formatLeaderboardName(3)).toBe('Leaderboard 3')
  })

  it('mirrors the exact fallback shape the API uses for an id it does not recognise', () => {
    expect(formatLeaderboardName(999)).toBe('Leaderboard 999')
  })
})
