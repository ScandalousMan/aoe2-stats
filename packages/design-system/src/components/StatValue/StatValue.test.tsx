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

  it('renders a secondary-colour em dash, never text-primary, when the value has never been observed', () => {
    render(<StatValue label="Rank" status="empty" secondaryLine="Not ranked yet" />)
    const dash = screen.getByText('—')
    expect(dash.className).toMatch(/text-text-secondary/)
    expect(dash.className).not.toMatch(/text-text-primary/)
    expect(screen.getByText('Not ranked yet')).toBeInTheDocument()
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
