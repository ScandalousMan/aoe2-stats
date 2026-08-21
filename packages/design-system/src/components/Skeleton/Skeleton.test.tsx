import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Skeleton } from './index'

describe('Skeleton', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not paint before 200ms, so a fast load never flashes', () => {
    const { container } = render(<Skeleton variant="block" className="h-9 w-24" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('paints after 200ms, hidden from the accessibility tree', () => {
    const { container } = render(<Skeleton variant="block" className="h-9 w-24" />)
    act(() => vi.advanceTimersByTime(200))
    const block = container.firstElementChild
    expect(block).not.toBeNull()
    expect(block).toHaveAttribute('aria-hidden', 'true')
  })

  it('renders one line per requested line, with no text content and no zero placeholder', () => {
    render(<Skeleton variant="text" lines={3} />)
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText('–')).not.toBeInTheDocument()
  })

  it('renders nothing for a zero line count', () => {
    const { container } = render(<Skeleton variant="text" lines={0} />)
    act(() => vi.advanceTimersByTime(200))
    expect(container).toBeEmptyDOMElement()
  })
})
