import { act, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchList, MatchRow } from './index'
import type { MatchRowData } from './index'

const match: MatchRowData = {
  gameId: '1001',
  href: '/matches/1001',
  outcome: 'win',
  opponent: { alias: 'aoe2villain' },
  map: 'Arabia',
  civilisation: 'Franks',
  ratingChange: { value: 12 },
  durationLabel: '34 min',
  playedAtRelative: '3 hours ago',
  playedAtAbsolute: '2026-08-22T09:12:00Z',
  captureStatus: 'stored',
  captureDeadlineAt: null,
}

describe('MatchRow', () => {
  it('renders the whole card as a single link, and everything inside it as non-interactive text', () => {
    render(<MatchRow match={match} />)
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/matches/1001')
    expect(within(links[0]).queryAllByRole('button')).toHaveLength(0)
  })

  it('shows "Win"/"Loss" as text, never colour alone', () => {
    const { rerender } = render(<MatchRow match={match} />)
    expect(screen.getByText('Win')).toBeInTheDocument()
    rerender(<MatchRow match={{ ...match, outcome: 'loss' }} />)
    expect(screen.getByText('Loss')).toBeInTheDocument()
  })

  it('names the first opposing participant and appends "and N others" for a team match', () => {
    render(<MatchRow match={{ ...match, opponent: { alias: 'aoe2villain', othersCount: 3 } }} />)
    expect(screen.getByText('aoe2villain and 3 others')).toBeInTheDocument()
  })

  it('never shows a bare count with no name for a team match', () => {
    render(<MatchRow match={{ ...match, opponent: { alias: 'aoe2villain', othersCount: 3 } }} />)
    expect(screen.queryByText(/^3 others$/)).not.toBeInTheDocument()
  })

  it('shows an explicit sign on the rating change', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('+12')).toBeInTheDocument()
  })

  it('renders no rating change field when the match carries none', () => {
    render(<MatchRow match={{ ...match, ratingChange: undefined }} />)
    expect(screen.queryByText('Rating change')).not.toBeInTheDocument()
  })

  it('shows the map and civilisation as plain text, never an emblem image', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText('Franks')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('shows the duration pre-formatted, never raw seconds', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('34 min')).toBeInTheDocument()
  })

  it('shows the relative time with the absolute time available as a title tooltip', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('3 hours ago')).toHaveAttribute('title', '2026-08-22T09:12:00Z')
  })

  it('renders the capture-state badge collapsed to one of the four labels', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('Archived')).toBeInTheDocument()
  })

  it('renders no badge at all for a match with no ReplayCapture row yet', () => {
    render(<MatchRow match={{ ...match, captureStatus: null }} />)
    expect(screen.queryByText(/archived|catchable|lost|review/i)).not.toBeInTheDocument()
  })
})

describe('MatchList', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows exactly 5 skeleton rows while loading', () => {
    const { container } = render(<MatchList status="loading" />)
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(5)
  })

  it('shows a danger callout with a working retry on error', async () => {
    const onRetry = vi.fn()
    render(<MatchList status="error" onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load your match history')
    const button = screen.getByRole('button', { name: 'Try again' })
    button.click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows an info callout when there are zero matches', () => {
    render(<MatchList status="empty" />)
    expect(screen.getByRole('status')).toHaveTextContent('No matches yet')
    expect(screen.getByRole('status')).toHaveTextContent('Once you play, they will appear here.')
  })

  it('also treats an explicit empty array as the empty state', () => {
    render(<MatchList matches={[]} />)
    expect(screen.getByRole('status')).toHaveTextContent('No matches yet')
  })

  it('renders one card per match, reverse-chronological order preserved as given', () => {
    const second: MatchRowData = {
      ...match,
      gameId: '1002',
      href: '/matches/1002',
      opponent: { alias: 'someoneElse' },
    }
    render(<MatchList matches={[match, second]} />)
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/matches/1001')
    expect(links[1]).toHaveAttribute('href', '/matches/1002')
  })

  it("renders every seeded row's capture state, never dropping one", () => {
    const lost: MatchRowData = { ...match, gameId: '1003', captureStatus: 'unavailable' }
    const review: MatchRowData = { ...match, gameId: '1004', captureStatus: 'quarantined' }
    render(<MatchList matches={[match, lost, review]} />)
    expect(screen.getByText('Archived')).toBeInTheDocument()
    expect(screen.getByText('Lost')).toBeInTheDocument()
    expect(screen.getByText('Needs review')).toBeInTheDocument()
  })

  it('renders a real ruled table with a caption from `lg` up, never both layouts at once', () => {
    const original = window.matchMedia
    window.matchMedia = (query: string) =>
      ({
        matches: query.includes('1024'),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList
    render(<MatchList matches={[match]} />)
    expect(screen.getByRole('table', { name: 'Your recent matches' })).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    window.matchMedia = original
  })
})
