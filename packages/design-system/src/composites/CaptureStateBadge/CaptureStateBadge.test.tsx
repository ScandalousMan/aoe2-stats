import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CaptureStateBadge } from './index'

function inFromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString()
}

describe('CaptureStateBadge', () => {
  it('renders "Archived" — never "Safe" — for a stored capture', () => {
    render(<CaptureStateBadge captureStatus="stored" />)
    expect(screen.getByText('Archived')).toBeInTheDocument()
    expect(screen.queryByText(/safe/i)).not.toBeInTheDocument()
  })

  it('collapses both pending and downloading to "Still catchable"', () => {
    const { unmount } = render(
      <CaptureStateBadge captureStatus="pending" captureDeadlineAt={inFromNow(60_000)} />,
    )
    expect(screen.getByText('Still catchable')).toBeInTheDocument()
    unmount()

    render(<CaptureStateBadge captureStatus="downloading" captureDeadlineAt={inFromNow(60_000)} />)
    expect(screen.getByText('Still catchable')).toBeInTheDocument()
  })

  it.each(['unavailable', 'expired', 'failed'] as const)(
    'collapses %s to "Lost" with its own reason as SecondaryLine',
    (status) => {
      render(<CaptureStateBadge captureStatus={status} />)
      expect(screen.getByText('Lost')).toBeInTheDocument()
    },
  )

  it('the three "Lost" statuses show three different reasons', () => {
    const { unmount: unmount1 } = render(<CaptureStateBadge captureStatus="unavailable" />)
    const unavailableText = screen.getByText(/saved games folder/)
    unmount1()

    const { unmount: unmount2 } = render(<CaptureStateBadge captureStatus="expired" />)
    const expiredText = screen.getByText(/did not capture it in time/)
    unmount2()

    render(<CaptureStateBadge captureStatus="failed" />)
    const failedText = screen.getByText(/repeated attempts/)

    expect(unavailableText.textContent).not.toBe(expiredText.textContent)
    expect(expiredText.textContent).not.toBe(failedText.textContent)
  })

  it('renders "Needs review" for a quarantined capture, with its own explanation', () => {
    render(<CaptureStateBadge captureStatus="quarantined" />)
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByText(/failed validation/)).toBeInTheDocument()
  })

  it('associates the SecondaryLine with the pill via aria-describedby', () => {
    render(<CaptureStateBadge captureStatus="expired" />)
    const wrapper = screen.getByText('Lost').closest('span[aria-describedby]')
    const describedBy = wrapper?.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      /did not capture it in time/,
    )
  })

  // T722 (capture-state-badge.md §3, "`withdrawn` is a fifth state"): the write that sets it read
  // ownership as it ran, and the sentence claims nothing about the deadline, the source, what the
  // row holds or what to do next.
  describe('withdrawn — a fifth state, known, never the unknown-status fallback', () => {
    const WITHDRAWN_SENTENCE =
      'Automatic capture ended for this match while archival was not running for this profile.'

    it('detail: reads "Not archived" in the neutral paint, with the sentence and never the raw word', () => {
      const { container } = render(<CaptureStateBadge captureStatus="withdrawn" variant="detail" />)
      const pill = screen.getByText('Not archived')
      expect(pill.className).toContain('bg-surface-sunken')
      expect(pill.className).not.toContain('text-danger')
      expect(screen.getByText(WITHDRAWN_SENTENCE)).toBeInTheDocument()
      expect(container).not.toHaveTextContent(/withdrawn/i)
    })

    it('detail: associates the sentence with the pill via aria-describedby', () => {
      render(<CaptureStateBadge captureStatus="withdrawn" variant="detail" />)
      const wrapper = screen.getByText('Not archived').closest('span[aria-describedby]')
      const describedBy = wrapper?.getAttribute('aria-describedby')
      expect(describedBy).toBeTruthy()
      expect(document.getElementById(describedBy as string)).toHaveTextContent(WITHDRAWN_SENTENCE)
    })

    it('compact: the pill alone — no sentence and no aria-describedby', () => {
      const { container } = render(
        <CaptureStateBadge captureStatus="withdrawn" variant="compact" />,
      )
      const pill = screen.getByText('Not archived')
      expect(pill.className).toContain('bg-surface-sunken')
      expect(container).toHaveTextContent(/^Not archived$/)
      expect(container.querySelector('[aria-describedby]')).toBeNull()
      expect(screen.queryByText(/archival was not running/i)).not.toBeInTheDocument()
      expect(container).not.toHaveTextContent(/withdrawn/i)
    })

    it('compact is the default variant, so a bare withdrawn badge is also the pill alone', () => {
      const { container } = render(<CaptureStateBadge captureStatus="withdrawn" />)
      expect(container).toHaveTextContent(/^Not archived$/)
    })

    // The contrast cases: `withdrawn` was added as a known state, not by loosening the fallback.
    it.each(['compact', 'detail'] as const)(
      'an unknown status still renders the neutral fallback carrying the raw word (%s)',
      (variant) => {
        const { container } = render(
          <CaptureStateBadge captureStatus="something_new" variant={variant} />,
        )
        const pill = screen.getByText('something_new')
        expect(pill.className).toContain('bg-surface-sunken')
        expect(container).toHaveTextContent(/^something_new$/)
        expect(container.querySelector('[aria-describedby]')).toBeNull()
        expect(screen.queryByText('Not archived')).not.toBeInTheDocument()
      },
    )

    it.each(['compact', 'detail'] as const)(
      'expired still reads "Lost" in danger with its reason (%s)',
      (variant) => {
        render(<CaptureStateBadge captureStatus="expired" variant={variant} />)
        expect(screen.getByText('Lost').className).toContain('text-danger')
        expect(screen.getByText(/did not capture it in time/)).toBeInTheDocument()
        expect(screen.queryByText('Not archived')).not.toBeInTheDocument()
      },
    )
  })

  it('renders nothing when no capture row exists yet (empty)', () => {
    const { container } = render(<CaptureStateBadge captureStatus={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a neutral badge with the raw value for an unrecognised status (error), never a guessed tone', () => {
    render(<CaptureStateBadge captureStatus="a_future_status" />)
    const badge = screen.getByText('a_future_status')
    expect(badge.className).toContain('bg-surface-sunken')
  })

  it('renders a Skeleton in place of the badge while loading, regardless of captureStatus', () => {
    vi.useFakeTimers()
    const { container } = render(<CaptureStateBadge captureStatus="stored" loading />)
    expect(screen.queryByText('Archived')).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('shows the still-catchable pill with no SecondaryLine when the deadline is missing', () => {
    render(<CaptureStateBadge captureStatus="pending" captureDeadlineAt={null} />)
    expect(screen.getByText('Still catchable')).toBeInTheDocument()
    expect(screen.queryByText(/left$/)).not.toBeInTheDocument()
  })

  describe('the countdown', () => {
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-08-22T12:00:00Z'))
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('shows a days countdown for a deadline several days out', () => {
      const deadline = new Date('2026-08-28T12:00:00Z').toISOString()
      render(<CaptureStateBadge captureStatus="pending" captureDeadlineAt={deadline} />)
      expect(screen.getByText('6 days left')).toBeInTheDocument()
    })

    it('never shows a negative countdown once the deadline has passed while still pending', () => {
      const deadline = new Date('2026-08-22T11:00:00Z').toISOString()
      render(<CaptureStateBadge captureStatus="pending" captureDeadlineAt={deadline} />)
      expect(screen.getByText('Capture window closing')).toBeInTheDocument()
      expect(screen.queryByText(/^-/)).not.toBeInTheDocument()
    })

    it('recomputes on an interval no coarser than once per minute while mounted', () => {
      const deadline = new Date('2026-08-22T12:05:00Z').toISOString()
      render(<CaptureStateBadge captureStatus="pending" captureDeadlineAt={deadline} />)
      expect(screen.getByText('5 minutes left')).toBeInTheDocument()

      act(() => vi.advanceTimersByTime(3 * 60_000))

      expect(screen.getByText('2 minutes left')).toBeInTheDocument()
    })

    it('renders the full-sentence form in the detail variant', () => {
      const deadline = new Date('2026-08-28T12:00:00Z').toISOString()
      render(
        <CaptureStateBadge captureStatus="pending" captureDeadlineAt={deadline} variant="detail" />,
      )
      expect(screen.getByText('Captures automatically within 6 days.')).toBeInTheDocument()
    })
  })

  describe('`stacked` — told to stack, rather than inferring the window is its own box', () => {
    it('stacks the pill and SecondaryLine in compact variant when `stacked` is set', () => {
      render(<CaptureStateBadge captureStatus="expired" variant="compact" stacked />)
      const wrapper = screen.getByText('Lost').closest('div')
      expect(wrapper?.className).toContain('flex-col')
      expect(wrapper?.className).not.toContain('sm:flex-row')
    })

    it('leaves compact variant free to respond to the window when `stacked` is not set', () => {
      render(<CaptureStateBadge captureStatus="expired" variant="compact" />)
      const wrapper = screen.getByText('Lost').closest('div')
      expect(wrapper?.className).toContain('sm:flex-row')
    })

    it('has no effect on detail variant, which already always stacks', () => {
      render(<CaptureStateBadge captureStatus="expired" variant="detail" stacked={false} />)
      const wrapper = screen.getByText('Lost').closest('div')
      expect(wrapper?.className).toContain('flex-col')
      expect(wrapper?.className).not.toContain('sm:flex-row')
    })
  })
})
