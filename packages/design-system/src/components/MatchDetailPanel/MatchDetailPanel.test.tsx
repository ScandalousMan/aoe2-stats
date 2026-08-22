import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchDetailPanel } from './index'
import type { MatchDetailData } from './index'

const match: MatchDetailData = {
  gameId: '1001',
  map: 'Arabia',
  leaderboardName: '1v1 Random Map',
  durationLabel: '34 min',
  playedAtLabel: '22 Aug 2026, 14:32',
  captureStatus: 'stored',
  captureDeadlineAt: null,
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'aoe2guy',
          civilisation: 'Franks',
          result: 'win',
          ratingChange: { value: 12 },
        },
      ],
    },
    {
      id: 'team-2',
      name: 'Team 2',
      participants: [
        {
          id: 'p2',
          alias: 'aoe2villain',
          civilisation: 'Mongols',
          result: 'loss',
          ratingChange: { value: -12 },
        },
      ],
    },
  ],
}

describe('MatchDetailPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the map, leaderboard and duration', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText(/1v1 Random Map/)).toBeInTheDocument()
    expect(screen.getByText(/34 min/)).toBeInTheDocument()
  })

  it('shows the DownloadAction only for a stored capture', () => {
    const { rerender } = render(<MatchDetailPanel match={match} />)
    expect(screen.getByRole('button', { name: 'Download replay' })).toBeInTheDocument()

    rerender(<MatchDetailPanel match={{ ...match, captureStatus: 'pending' }} />)
    expect(screen.queryByRole('button', { name: 'Download replay' })).not.toBeInTheDocument()
  })

  it('never shows the DownloadAction for a quarantined capture, disabled or otherwise', () => {
    render(<MatchDetailPanel match={{ ...match, captureStatus: 'quarantined' }} />)
    expect(screen.queryByRole('button', { name: 'Download replay' })).not.toBeInTheDocument()
  })

  it('shows a loading label while the signed URL is being requested', () => {
    render(<MatchDetailPanel match={match} downloadState="loading" />)
    expect(screen.getByRole('button', { name: /Preparing your download/ })).toBeInTheDocument()
  })

  it('returns the download button to default and pressable on failure, with a reason in StatusRegion', () => {
    render(<MatchDetailPanel match={match} downloadState="error" />)
    const button = screen.getByRole('button', { name: 'Download replay' })
    expect(button).toBeEnabled()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The download link could not be created. Try again.',
    )
  })

  it('groups every participant under the correct team heading, with none duplicated or dropped', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('Team 1')).toBeInTheDocument()
    expect(screen.getByText('Team 2')).toBeInTheDocument()
    expect(screen.getAllByText('aoe2guy')).toHaveLength(1)
    expect(screen.getAllByText('aoe2villain')).toHaveLength(1)
  })

  it("shows an explicit sign on each participant's rating change", () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('+12')).toBeInTheDocument()
    expect(screen.getByText('−12')).toBeInTheDocument()
  })

  it('shows a load-failed callout with a retry, distinct wording from not-found', () => {
    const onRetry = vi.fn()
    render(<MatchDetailPanel status="error" onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load this match')
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows a single not-found callout with a link back to the match list, revealing nothing that distinguishes "does not exist" from "not yours"', () => {
    render(<MatchDetailPanel status="not-found" matchListHref="/matches" />)
    expect(screen.getByRole('alert')).toHaveTextContent('This match could not be found.')
    const link = screen.getByRole('link', { name: 'Back to the match list' })
    expect(link).toHaveAttribute('href', '/matches')
    expect(screen.queryByText(/not yours|does not exist|unauthorized/i)).not.toBeInTheDocument()
  })

  it("shows skeleton header fields and the badge's own loading state while loading", () => {
    const { container } = render(<MatchDetailPanel status="loading" />)
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
    expect(screen.queryByText('Arabia')).not.toBeInTheDocument()
  })

  it('never shows the DownloadAction while loading', () => {
    render(<MatchDetailPanel status="loading" />)
    expect(screen.queryByRole('button', { name: /Download/ })).not.toBeInTheDocument()
  })
})

describe('MatchDetailPanel — ParticipantsTable responsive tiers (match-history.md §8)', () => {
  function mockMatchMediaAt(widthPx: number): () => void {
    const original = window.matchMedia
    window.matchMedia = (query: string) => {
      const minWidthMatch = /min-width:\s*(\d+)px/.exec(query)
      const threshold = minWidthMatch ? Number(minWidthMatch[1]) : Infinity
      return {
        matches: widthPx >= threshold,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      } as MediaQueryList
    }
    return () => {
      window.matchMedia = original
    }
  }

  it('renders one card per participant at 375, no table', () => {
    const restore = mockMatchMediaAt(375)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    restore()
  })

  it('still renders cards, not a table, at 1100 — below `xl`, the breakpoint the spec names for the table', () => {
    const restore = mockMatchMediaAt(1100)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    restore()
  })

  it('renders participant cards two-up (a 2-column grid) at 768, still no table', () => {
    const restore = mockMatchMediaAt(768)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    const lists = screen.getAllByRole('list')
    expect(lists).toHaveLength(2)
    for (const list of lists) {
      expect(list.className).toContain('grid-cols-2')
    }
    restore()
  })

  it('renders a real ruled table with a caption per team from `xl` (1280) up', () => {
    const restore = mockMatchMediaAt(1280)
    render(<MatchDetailPanel match={match} />)
    expect(screen.getAllByRole('table', { name: /Team/ })).toHaveLength(2)
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    restore()
  })
})
