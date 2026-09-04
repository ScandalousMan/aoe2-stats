import { describe, expect, it } from 'vitest'
import {
  formatCivilisation,
  formatDuration,
  formatDurationPrecise,
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

// T333 (match-detail defect): the list stays rounded (`formatDuration` above, untouched), but the
// match-detail page reads second precision — `formatDurationPrecise` is a second, separate
// function rather than a change to `formatDuration` itself, since the rendered list text is part
// of the CI-authoritative Playwright full-page baselines (never regenerated locally).
describe('formatDurationPrecise', () => {
  it('reads exact whole minutes with no " 0 s" tail', () => {
    expect(formatDurationPrecise(2040)).toBe('34 min')
  })

  it('reads minutes and seconds together', () => {
    expect(formatDurationPrecise(932)).toBe('15 min 32 s')
  })

  it('reads under a minute as seconds only, no "0 min" prefix', () => {
    expect(formatDurationPrecise(45)).toBe('45 s')
  })

  it('never shows raw seconds text for a null duration', () => {
    expect(formatDurationPrecise(null)).toBe('Unknown duration')
  })
})

describe('formatOutcome', () => {
  it('passes "win" through', () => {
    expect(formatOutcome('win')).toBe('win')
  })

  it('passes "loss" through', () => {
    expect(formatOutcome('loss')).toBe('loss')
  })

  // The reported production defect: `match_players.result` is `null` for every row this system
  // has written so far (`discover.py`'s own docstring), and coercing that gap to "loss" rendered
  // an eight-player match with no known result anywhere as eight losses — a confident, false
  // statement. `null` must read as unknown, never as a guessed defeat (match-history.md §2a).
  it('reads a null result as "unknown", never as a guessed "loss"', () => {
    expect(formatOutcome(null)).toBe('unknown')
  })

  it('reads an unrecognised result as "unknown" too, not as a guessed "loss"', () => {
    expect(formatOutcome('draw')).toBe('unknown')
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
