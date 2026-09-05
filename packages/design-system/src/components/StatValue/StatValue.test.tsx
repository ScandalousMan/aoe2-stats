import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StatValue } from './index'

describe('StatValue', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('never renders 0, – or -- while loading', () => {
    render(<StatValue label="1v1 Random Map" status="loading" />)
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText('–')).not.toBeInTheDocument()
    expect(screen.queryByText('--')).not.toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('states why in words, in secondary colour never text-primary, when the value has never been observed — never an em dash', () => {
    render(<StatValue label="Rank" status="empty" secondaryLine="Not ranked yet" />)
    expect(screen.queryByText('—')).not.toBeInTheDocument()
    const reason = screen.getByText('Not ranked yet')
    expect(reason.className).toMatch(/text-text-secondary/)
    expect(reason.className).not.toMatch(/text-text-primary/)
    // The caller's own `secondaryLine` is reused as the value slot's words rather than repeated a
    // second time beneath it.
    expect(screen.getAllByText('Not ranked yet')).toHaveLength(1)
  })

  it('falls back to a generic, honest reason when the empty value has neither an emptyReason nor a secondaryLine', () => {
    render(<StatValue label="Rank" status="empty" />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('prefers an explicit emptyReason over secondaryLine, and still renders a distinct secondaryLine beneath it', () => {
    render(
      <StatValue
        label="Rank"
        status="empty"
        emptyReason="Never played this leaderboard"
        secondaryLine="Checked 3 minutes ago"
      />,
    )
    expect(screen.getByText('Never played this leaderboard')).toBeInTheDocument()
    expect(screen.getByText('Checked 3 minutes ago')).toBeInTheDocument()
  })

  it('never renders a digit for a genuinely-zero delta or value, and a real zero still renders as data', () => {
    render(<StatValue label="Streak" value="0" delta={{ value: 0 }} />)
    const value = screen.getByText('0')
    expect(value.className).toMatch(/text-text-primary/)
    const delta = screen.getByText('+0')
    expect(delta.className).toMatch(/text-success/)
  })

  it('announces its own loading state as a busy region by default, correct for standalone use', () => {
    const { container } = render(<StatValue label="Rank" status="loading" />)
    expect(container.querySelector('dl')).toHaveAttribute('aria-busy', 'true')
  })

  it('does not announce its own loading state when composed by a caller that owns the region', () => {
    const { container } = render(
      <StatValue label="Rank" status="loading" announceLoading={false} />,
    )
    expect(container.querySelector('dl')).not.toHaveAttribute('aria-busy')
  })

  it('renders the stale value at full contrast alongside a secondary line explaining the staleness — never blank', () => {
    render(
      <StatValue
        label="1v1 Random Map"
        value="1842"
        secondaryLine="Measured 2 hours ago — refresh failed"
      />,
    )
    const value = screen.getByText('1842')
    expect(value.className).toMatch(/text-text-primary/)
    expect(screen.getByText('Measured 2 hours ago — refresh failed')).toBeInTheDocument()
  })

  it('renders an explicit sign character on the delta, never colour alone', () => {
    render(<StatValue label="1v1 Random Map" value="1842" delta={{ value: 12 }} />)
    const delta = screen.getByText('+12')
    expect(delta.className).toMatch(/text-success/)
  })

  it('renders a negative delta with a minus sign and the danger colour', () => {
    render(<StatValue label="1v1 Random Map" value="1802" delta={{ value: -8 }} />)
    const delta = screen.getByText('−8')
    expect(delta.className).toMatch(/text-danger/)
  })

  it('associates the label and the value with <dt>/<dd>', () => {
    render(<StatValue label="Win rate" value="54%" />)
    expect(screen.getByText('Win rate').tagName).toBe('DT')
    expect(screen.getByText('54%').closest('dd')).not.toBeNull()
  })
})
