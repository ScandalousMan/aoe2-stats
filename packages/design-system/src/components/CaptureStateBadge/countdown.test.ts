import { describe, expect, it } from 'vitest'
import { describeCaptureCountdown } from './countdown'

const NOW = new Date('2026-08-22T12:00:00Z').getTime()

function fromNow(offsetMs: number): string {
  return new Date(NOW + offsetMs).toISOString()
}

describe('describeCaptureCountdown', () => {
  it('uses days while at least one full day remains, floored', () => {
    // 6 days and 23 hours: still "6 days", never rounded up to 7.
    const deadline = fromNow(6 * 24 * 60 * 60_000 + 23 * 60 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('6 days left')
  })

  it('pluralises correctly for exactly one day', () => {
    const deadline = fromNow(24 * 60 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('1 day left')
  })

  it('drops to hours below one full day, floored', () => {
    const deadline = fromNow(18 * 60 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('18 hours left')
  })

  it('pluralises correctly for exactly one hour', () => {
    const deadline = fromNow(60 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('1 hour left')
  })

  it('drops to minutes below one full hour, floored, and never shows seconds', () => {
    const deadline = fromNow(42 * 60_000 + 59_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('42 minutes left')
  })

  it('pluralises correctly for exactly one minute', () => {
    const deadline = fromNow(60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('1 minute left')
  })

  it('renders the detail-context sentence form instead of the compact pill form', () => {
    const deadline = fromNow(6 * 24 * 60 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'detail')).toBe(
      'Captures automatically within 6 days.',
    )
  })

  it('never returns a negative countdown once the deadline has passed', () => {
    const deadline = fromNow(-5 * 60_000)
    expect(describeCaptureCountdown(deadline, NOW, 'compact')).toBe('Capture window closing')
    expect(describeCaptureCountdown(deadline, NOW, 'detail')).toBe(
      'This capture is due any moment.',
    )
  })

  it('treats a deadline at exactly now as passed, not as "0 minutes left"', () => {
    expect(describeCaptureCountdown(fromNow(0), NOW, 'compact')).toBe('Capture window closing')
  })
})
