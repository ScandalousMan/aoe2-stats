import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReplayAvailabilityRowData } from './index'
import { ReplayAvailabilityList } from './index'

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

describe('ReplayAvailabilityList', () => {
  it('renders the "Recorded games" heading even when every row is unobtainable (§5 empty)', () => {
    const rows: ReplayAvailabilityRowData[] = [
      { id: '1', alias: 'Liereyy', availability: 'expired' },
      { id: '2', alias: 'Yo', availability: 'never_recorded' },
    ]
    render(<ReplayAvailabilityList rows={rows} />)
    expect(screen.getByRole('heading', { name: 'Recorded games', level: 3 })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('gives all four states their own, never-shared label', () => {
    const rows: ReplayAvailabilityRowData[] = [
      { id: '1', alias: 'GL.TheViper', availability: 'archived' },
      { id: '2', alias: 'Hera', availability: 'obtainable', obtainableUntil: inFromNow(60_000) },
      { id: '3', alias: 'Liereyy', availability: 'expired' },
      { id: '4', alias: 'Yo', availability: 'never_recorded' },
    ]
    render(<ReplayAvailabilityList rows={rows} />)
    expect(screen.getByText('In our archive')).toBeInTheDocument()
    expect(screen.getByText('Obtainable')).toBeInTheDocument()
    expect(screen.getByText('Expired')).toBeInTheDocument()
    expect(screen.getByText('Never recorded')).toBeInTheDocument()
  })

  it('shows a DownloadAction only for archived and obtainable, never disabled for the other two', () => {
    const rows: ReplayAvailabilityRowData[] = [
      { id: '1', alias: 'GL.TheViper', availability: 'archived' },
      { id: '2', alias: 'Hera', availability: 'obtainable', obtainableUntil: null },
      { id: '3', alias: 'Liereyy', availability: 'expired' },
      { id: '4', alias: 'Yo', availability: 'never_recorded' },
    ]
    render(<ReplayAvailabilityList rows={rows} />)
    const buttons = screen.getAllByRole('button', { name: 'Download' })
    expect(buttons).toHaveLength(2)
    buttons.forEach((button) => expect(button).not.toBeDisabled())
  })

  it('shows no SecondaryLine for an archived row', () => {
    render(
      <ReplayAvailabilityList
        rows={[{ id: '1', alias: 'GL.TheViper', availability: 'archived' }]}
      />,
    )
    const badge = screen.getByText('In our archive')
    const wrapper = badge.closest('span[aria-describedby]')
    expect(wrapper).toBeNull()
  })

  it('shows the exact, normative sentence for an expired row', () => {
    render(
      <ReplayAvailabilityList rows={[{ id: '1', alias: 'Liereyy', availability: 'expired' }]} />,
    )
    expect(
      screen.getByText('This recording is no longer available from the game.'),
    ).toBeInTheDocument()
  })

  it('shows the exact, normative sentence for a never_recorded row', () => {
    render(
      <ReplayAvailabilityList rows={[{ id: '1', alias: 'Yo', availability: 'never_recorded' }]} />,
    )
    expect(screen.getByText('The game did not record this point of view.')).toBeInTheDocument()
  })

  it('shows a different sentence for the boundary race than for a plain expired row', () => {
    render(
      <ReplayAvailabilityList
        rows={[{ id: '1', alias: 'MbL', availability: 'expired', expiredSincePageLoad: true }]}
      />,
    )
    expect(
      screen.getByText('This recording expired while you were viewing this page.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('This recording is no longer available from the game.'),
    ).not.toBeInTheDocument()
  })

  it('associates the SecondaryLine with its row badge via aria-describedby', () => {
    render(
      <ReplayAvailabilityList rows={[{ id: '1', alias: 'Liereyy', availability: 'expired' }]} />,
    )
    const wrapper = screen.getByText('Expired').closest('span[aria-describedby]')
    const describedBy = wrapper?.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      'This recording is no longer available from the game.',
    )
  })

  describe('obtainable_until: null (FR-024, amended 2026-08-29)', () => {
    it('renders the identical badge and tone as a dated row, with no SecondaryLine and no invented date', () => {
      render(
        <ReplayAvailabilityList
          rows={[{ id: '1', alias: 'TaToH', availability: 'obtainable', obtainableUntil: null }]}
        />,
      )
      const badge = screen.getByText('Obtainable')
      expect(badge.className).toContain('text-info')
      expect(badge.closest('span[aria-describedby]')).toBeNull()
      expect(screen.queryByText(/left$/)).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
    })
  })

  describe('the countdown, reused from CaptureStateBadge/countdown.ts', () => {
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-08-22T12:00:00Z'))
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('shows a days countdown for a deadline several days out', () => {
      const obtainableUntil = new Date('2026-08-28T12:00:00Z').toISOString()
      render(
        <ReplayAvailabilityList
          rows={[{ id: '1', alias: 'Hera', availability: 'obtainable', obtainableUntil }]}
        />,
      )
      expect(screen.getByText('6 days left')).toBeInTheDocument()
    })

    it('shows an hours countdown for a match a few hours from the boundary, not days rounded up', () => {
      const obtainableUntil = new Date('2026-08-22T15:00:00Z').toISOString()
      render(
        <ReplayAvailabilityList
          rows={[{ id: '1', alias: 'DauT', availability: 'obtainable', obtainableUntil }]}
        />,
      )
      expect(screen.getByText('3 hours left')).toBeInTheDocument()
      expect(screen.queryByText(/day/)).not.toBeInTheDocument()
    })

    it('recomputes on an interval no coarser than once per minute while mounted', () => {
      const obtainableUntil = new Date('2026-08-22T12:05:00Z').toISOString()
      render(
        <ReplayAvailabilityList
          rows={[{ id: '1', alias: 'Hera', availability: 'obtainable', obtainableUntil }]}
        />,
      )
      expect(screen.getByText('5 minutes left')).toBeInTheDocument()

      act(() => vi.advanceTimersByTime(3 * 60_000))

      expect(screen.getByText('2 minutes left')).toBeInTheDocument()
    })

    it('renders no SecondaryLine, never a negative or borrowed sentence, once obtainableUntil has passed', () => {
      const obtainableUntil = new Date('2026-08-22T11:00:00Z').toISOString()
      render(
        <ReplayAvailabilityList
          rows={[{ id: '1', alias: 'Hera', availability: 'obtainable', obtainableUntil }]}
        />,
      )
      expect(screen.getByText('Obtainable')).toBeInTheDocument()
      expect(screen.queryByText(/left$/)).not.toBeInTheDocument()
      expect(screen.queryByText(/closing/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/^-/)).not.toBeInTheDocument()
    })
  })

  describe('download failure', () => {
    it('keeps the row default and pressable, with a danger alert, when the request could not start', () => {
      render(
        <ReplayAvailabilityList
          rows={[
            {
              id: '1',
              alias: 'GL.TheViper',
              availability: 'archived',
              downloadState: 'error',
            },
          ]}
        />,
      )
      const button = screen.getByRole('button', { name: 'Download' })
      expect(button).not.toBeDisabled()
      expect(
        within(screen.getByRole('alert')).getByText('We could not start that download. Try again.'),
      ).toBeInTheDocument()
    })

    it('names the exact retry_after seconds for a rate-limited row, never rounded or invented', () => {
      render(
        <ReplayAvailabilityList
          rows={[
            {
              id: '1',
              alias: 'GL.TheViper',
              availability: 'archived',
              downloadState: 'rate_limited',
              retryAfterSeconds: 42,
            },
          ]}
        />,
      )
      expect(
        within(screen.getByRole('alert')).getByText(
          'You are downloading too quickly. Try again in 42 seconds.',
        ),
      ).toBeInTheDocument()
    })

    it('shows the Button loading state while a download is being prepared', () => {
      render(
        <ReplayAvailabilityList
          rows={[
            { id: '1', alias: 'GL.TheViper', availability: 'archived', downloadState: 'loading' },
          ]}
        />,
      )
      const button = screen.getByRole('button', { name: 'Preparing your download…' })
      expect(button).toHaveAttribute('aria-busy', 'true')
    })
  })

  it('calls onDownload with the row id, not the alias or any other value', async () => {
    const onDownload = vi.fn()
    const user = userEvent.setup()
    render(
      <ReplayAvailabilityList
        rows={[{ id: 'row-7', alias: 'GL.TheViper', availability: 'archived' }]}
        onDownload={onDownload}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Download' }))
    expect(onDownload).toHaveBeenCalledWith('row-7')
  })

  it('renders skeleton rows, not the real list, while loading', () => {
    vi.useFakeTimers()
    const { container } = render(
      <ReplayAvailabilityList
        loading
        rows={[{ id: '1', alias: 'GL.TheViper', availability: 'archived' }]}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Recorded games' })).toBeInTheDocument()
    expect(screen.queryByText('In our archive')).not.toBeInTheDocument()
    // Skeleton's own 200ms delay (`useDelayedVisible`) before it paints a pulse.
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(2)
    vi.useRealTimers()
  })

  it('announces loading once for the list, not once per skeleton row (FR-054)', () => {
    vi.useFakeTimers()
    const { container } = render(<ReplayAvailabilityList loading rows={[]} />)
    act(() => vi.advanceTimersByTime(200))
    vi.useRealTimers()

    expect(screen.getByRole('list')).toHaveAttribute('aria-busy', 'true')
    const hiddenBlocks = container.querySelectorAll('[aria-hidden="true"]')
    expect(hiddenBlocks).toHaveLength(2)
    for (const block of hiddenBlocks) {
      expect(block).not.toHaveAttribute('aria-busy')
    }
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(1)
  })

  it('does not mark the list busy once loaded', () => {
    render(
      <ReplayAvailabilityList
        rows={[{ id: '1', alias: 'GL.TheViper', availability: 'archived' }]}
      />,
    )
    expect(screen.getByRole('list')).not.toHaveAttribute('aria-busy')
  })
})
