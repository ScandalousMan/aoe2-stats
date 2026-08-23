import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PlayerSearchResultData } from '../PlayerResultRow'
import { SearchBox } from './index'
import type { SearchBoxState } from './index'

const results: PlayerSearchResultData[] = [
  {
    profileId: '1',
    href: '/players/1',
    alias: 'TheViper',
    country: 'Netherlands',
    gamesPlayed: 8213,
    clan: null,
  },
  {
    profileId: '2',
    href: '/players/2',
    alias: 'Hera',
    country: 'Israel',
    gamesPlayed: 5120,
    clan: 'GL',
  },
]

// A controlled input needs its owner to feed `onValueChange` back through `value` — this stands
// in for the route T322 builds, so the debounce tests below exercise the real controlled loop
// rather than a `value` prop that never changes.
function Harness({
  state,
  onSearch,
  onRetry,
  initialValue = '',
}: {
  state: SearchBoxState
  onSearch: (value: string) => void
  onRetry?: () => void
  initialValue?: string
}) {
  const [value, setValue] = useState(initialValue)
  return (
    <SearchBox
      value={value}
      onValueChange={setValue}
      onSearch={onSearch}
      state={state}
      onRetry={onRetry}
    />
  )
}

describe('SearchBox', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('associates the label with the input', () => {
    render(<Harness state={{ status: 'idle' }} onSearch={() => {}} />)
    expect(screen.getByLabelText('Search a player')).toHaveAttribute('type', 'search')
  })

  it('idle: shows a plain-text prompt, inside neither a status nor an alert region', () => {
    render(<Harness state={{ status: 'idle' }} onSearch={() => {}} />)
    expect(screen.getByText('Search for a player by name.')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('updates the input value immediately on every keystroke, independently of the debounced search', () => {
    render(<Harness state={{ status: 'idle' }} onSearch={() => {}} />)
    const input = screen.getByLabelText('Search a player')
    fireEvent.change(input, { target: { value: 'vip' } })
    expect(input).toHaveValue('vip')
  })

  it('dispatches onSearch once, debounceMs after the last keystroke, never before', () => {
    const onSearch = vi.fn()
    render(<Harness state={{ status: 'idle' }} onSearch={onSearch} />)
    const input = screen.getByLabelText('Search a player')
    fireEvent.change(input, { target: { value: 'vip' } })
    act(() => vi.advanceTimersByTime(299))
    expect(onSearch).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onSearch).toHaveBeenCalledExactlyOnceWith('vip')
  })

  it('never dispatches onSearch for a blank query', () => {
    const onSearch = vi.fn()
    render(<Harness state={{ status: 'idle' }} onSearch={onSearch} />)
    const input = screen.getByLabelText('Search a player')
    fireEvent.change(input, { target: { value: '   ' } })
    act(() => vi.advanceTimersByTime(1000))
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('loading: marks the region busy and shows 5 hidden skeleton rows by default', () => {
    const { container } = render(<Harness state={{ status: 'loading' }} onSearch={() => {}} />)
    expect(screen.getByRole('region', { name: 'Search results' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(5)
  })

  it('loading after a larger answered set never shrinks below the previous result count', () => {
    const sevenResults = Array.from({ length: 7 }, (_, index) => ({
      ...results[0],
      profileId: String(index),
    }))
    const { container, rerender } = render(
      <Harness
        state={{ status: 'answered', query: 'v', results: sevenResults, degraded: false }}
        onSearch={() => {}}
      />,
    )
    rerender(<Harness state={{ status: 'loading' }} onSearch={() => {}} />)
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(7)
  })

  it('default — found: renders one PlayerResultRow link per result, no DegradedBanner', () => {
    render(
      <Harness
        state={{ status: 'answered', query: 'v', results, degraded: false }}
        onSearch={() => {}}
      />,
    )
    expect(screen.getAllByRole('link')).toHaveLength(2)
    expect(screen.getByRole('link', { name: /TheViper/ })).toHaveAttribute('href', '/players/1')
    expect(screen.queryByText(/degraded/i)).not.toBeInTheDocument()
  })

  it('empty 1 of 3 — not found: an info status callout naming the query, distinct from a failure', () => {
    render(
      <Harness
        state={{ status: 'answered', query: 'xyzzy', results: [], degraded: false }}
        onSearch={() => {}}
      />,
    )
    const region = screen.getByRole('status')
    expect(region).toHaveTextContent('No player matches')
    expect(region).toHaveTextContent('xyzzy')
    expect(region).toHaveTextContent('Check the spelling, or try a shorter part of the name.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('empty 2 of 3 — degraded with results: the banner and at least one row render in the same frame', () => {
    render(
      <Harness
        state={{ status: 'answered', query: 'v', results: [results[0]], degraded: true }}
        onSearch={() => {}}
      />,
    )
    const banner = screen.getByRole('status')
    expect(banner).toHaveTextContent('Player search is temporarily degraded.')
    expect(screen.getByRole('link', { name: /TheViper/ })).toBeInTheDocument()
  })

  it('empty 2 of 3 — degraded and empty: exactly one callout, carrying both sentences', () => {
    render(
      <Harness
        state={{ status: 'answered', query: 'xyzzy', results: [], degraded: true }}
        onSearch={() => {}}
      />,
    )
    expect(screen.getAllByRole('status')).toHaveLength(1)
    const banner = screen.getByRole('status')
    expect(banner).toHaveTextContent('Player search is temporarily degraded.')
    expect(banner).toHaveTextContent('No locally known player matches')
    expect(banner).toHaveTextContent('xyzzy')
    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  it('not-found and degraded never share the same wording', () => {
    const { rerender } = render(
      <Harness
        state={{ status: 'answered', query: 'x', results: [], degraded: false }}
        onSearch={() => {}}
      />,
    )
    const notFoundText = screen.getByRole('status').textContent
    rerender(
      <Harness
        state={{ status: 'answered', query: 'x', results: [], degraded: true }}
        onSearch={() => {}}
      />,
    )
    const degradedText = screen.getByRole('status').textContent
    expect(notFoundText).not.toEqual(degradedText)
  })

  it('error — rate limited: disables the input, shows the countdown, and describes why', () => {
    render(<Harness state={{ status: 'rate-limited', retryAfterSeconds: 3 }} onSearch={() => {}} />)
    const input = screen.getByLabelText('Search a player')
    expect(input).toBeDisabled()
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    const description = document.getElementById(describedBy as string)
    expect(description).toHaveTextContent("You're searching too quickly. Try again in 3s.")
    expect(within(description as HTMLElement).getByRole('status')).toBeInTheDocument()
  })

  it('error — rate limited: the input re-enables itself the instant the countdown reaches zero', () => {
    render(<Harness state={{ status: 'rate-limited', retryAfterSeconds: 2 }} onSearch={() => {}} />)
    const input = screen.getByLabelText('Search a player')
    expect(input).toBeDisabled()
    act(() => vi.advanceTimersByTime(2000))
    expect(input).not.toBeDisabled()
  })

  it('error — request failed: a danger alert distinct from the rate-limited warning, with a working retry', () => {
    const onRetry = vi.fn()
    render(<Harness state={{ status: 'failed' }} onSearch={() => {}} onRetry={onRetry} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('We could not search right now.')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
