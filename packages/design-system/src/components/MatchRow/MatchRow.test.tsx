import { readFileSync } from 'node:fs'
import path from 'node:path'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchList, MatchRow } from './index'
import type { MatchRowData } from './index'

// jsdom has no layout engine (vitest.config.ts): `getBoundingClientRect` always returns 0 here, so
// the touch-target assertion below cannot render a real box and measure it. The next best thing —
// `Menu.test.tsx`'s own precedent for T035d — is to read the real spacing scale from its single
// source of truth, `tokens/space.json`, and derive the pixel height a `Button`'s `h-<n>` utility
// actually resolves to from *that* number, not from a literal copied into the test. A class-name
// match (`toMatch(/h-12/)`) keeps passing even if the spacing unit that "12" multiplies shrinks;
// this fails the moment it would.
const SPACE_TOKENS_PATH = path.resolve(__dirname, '../../../tokens/space.json')
const ROOT_FONT_SIZE_PX = 16 // jsdom's default <html> font-size, same as an un-overridden browser.

function spacingUnitPx(): number {
  const { unit } = JSON.parse(readFileSync(SPACE_TOKENS_PATH, 'utf8')) as { unit: string }
  const remMatch = /^([\d.]+)rem$/.exec(unit)
  if (!remMatch) throw new Error(`tokens/space.json "unit" is not a rem value: ${unit}`)
  return Number.parseFloat(remMatch[1]) * ROOT_FONT_SIZE_PX
}

/** Stands in for jsdom's missing layout engine: derives the height a rendered element's own
 * `h-<n>` utility actually resolves to, from the real spacing token, instead of hardcoding a pixel
 * count in the test. An element with no such class measures as 0, so a `Button` that stops setting
 * an explicit height at all fails loudly rather than reading as compliant. */
function mockButtonHeightLayout() {
  const unitPx = spacingUnitPx()
  return vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: Element,
  ) {
    const match = /\bh-(\d+)\b/.exec(this.className)
    const height = match ? Number.parseInt(match[1], 10) * unitPx : 0
    return {
      height,
      width: 0,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      x: 0,
      y: 0,
      toJSON: () => {},
    } as DOMRect
  })
}

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

  // T388: a raw `<a href>` forces a full document reload inside a TanStack Router SPA.
  describe('onNavigate (T388)', () => {
    it('stays a real link to the match route, href included, when onNavigate is wired', () => {
      render(<MatchRow match={match} onNavigate={() => {}} />)
      expect(screen.getByRole('link')).toHaveAttribute('href', '/matches/1001')
    })

    it('calls onNavigate and prevents the default navigation for a plain left click', async () => {
      const onNavigate = vi.fn()
      const user = userEvent.setup()
      render(<MatchRow match={match} onNavigate={onNavigate} />)

      await user.click(screen.getByRole('link'))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/matches/1001')
    })

    it('lets a modified click (new tab) fall through to native handling, never calling onNavigate', () => {
      // Not prevented on purpose (this is the point of the test): jsdom then tries a real
      // navigation it does not implement and logs it asynchronously, after this test has already
      // finished — harmless, expected noise, not a signal to fix.
      const onNavigate = vi.fn()
      render(<MatchRow match={match} onNavigate={onNavigate} />)

      fireEvent.click(screen.getByRole('link'), { ctrlKey: true })

      expect(onNavigate).not.toHaveBeenCalled()
    })
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

  it('renders a real ruled table with a caption from `xl` (1280) up, never both layouts at once', () => {
    const restore = mockMatchMediaAt(1280)
    render(<MatchList matches={[match]} />)
    expect(screen.getByRole('table', { name: 'Your recent matches' })).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    restore()
  })

  // Regression: `lg` (1024) previously drove this switch, so a viewport of 1100 — above `lg`,
  // below the `xl` (1280) the spec actually reserves for the table (match-history.md §8) —
  // rendered a table when it should still show cards.
  it('still renders cards, not a table, at 1100 — below `xl`', () => {
    const restore = mockMatchMediaAt(1100)
    render(<MatchList matches={[match]} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    restore()
  })

  // T074b: the error-state retry control is reachable on a touch viewport and must clear the 44px
  // floor (shared-primitives.md's Button rule). Measured, not matched against a class name (T035d)
  // — see `mockButtonHeightLayout` above.
  it("the error-state 'Try again' rendered box clears the 44px touch floor", () => {
    const getBoundingClientRect = mockButtonHeightLayout()
    try {
      render(<MatchList status="error" onRetry={() => {}} />)
      const button = screen.getByRole('button', { name: 'Try again' })
      expect(button.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })

  // T074b: the table column gap (match-history.md §7).
  it('renders the table column gap at space-5 (pr-5), not space-6', () => {
    const restore = mockMatchMediaAt(1280)
    const { container } = render(<MatchList matches={[match]} />)
    const headerCell = container.querySelector('th')
    expect(headerCell?.className).toMatch(/\bpr-5\b/)
    expect(headerCell?.className).not.toMatch(/\bpr-6\b/)
    restore()
  })

  // T388: `onNavigate` must reach the row's link in both DOM layouts `MatchList` renders — the
  // card list below `xl` and the real `<table>` from `xl` up — never only one of them.
  describe('onNavigate (T388)', () => {
    // `fireEvent`, not `userEvent`: this describe block runs under `vi.useFakeTimers()`, and
    // `userEvent`'s own internal delays hang forever waiting on real timers that never advance.
    it('forwards onNavigate to the card-layout row link below xl', () => {
      const onNavigate = vi.fn()
      render(<MatchList matches={[match]} onNavigate={onNavigate} />)

      fireEvent.click(screen.getByRole('link'))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/matches/1001')
    })

    it('forwards onNavigate to the table-layout row link from xl up', () => {
      const restore = mockMatchMediaAt(1280)
      const onNavigate = vi.fn()
      render(<MatchList matches={[match]} onNavigate={onNavigate} />)

      fireEvent.click(screen.getByRole('link'))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/matches/1001')
      restore()
    })
  })

  // §11.3 (003, US2): `subject="other"` swaps the caption and the empty-state sentence, and
  // nothing else — the row itself carries no `subject` prop at all.
  describe('subject="other" (003 spec §11.3)', () => {
    it('defaults to the caller\'s own "Your recent matches" caption at xl', () => {
      const restore = mockMatchMediaAt(1280)
      render(<MatchList matches={[match]} />)
      expect(screen.getByRole('table', { name: 'Your recent matches' })).toBeInTheDocument()
      restore()
    })

    it('names the viewed player in the table caption instead of "Your"', () => {
      const restore = mockMatchMediaAt(1280)
      render(<MatchList matches={[match]} subject="other" subjectAlias="aoe2villain" />)
      expect(
        screen.getByRole('table', { name: "aoe2villain's recent matches" }),
      ).toBeInTheDocument()
      expect(screen.queryByText(/^Your recent matches$/)).not.toBeInTheDocument()
      restore()
    })

    it('names the viewed player in the accessible list name below xl too', () => {
      render(<MatchList matches={[match]} subject="other" subjectAlias="aoe2villain" />)
      expect(screen.getByRole('list', { name: "aoe2villain's recent matches" })).toBeInTheDocument()
    })

    it('shows the third-party empty-state sentence, never the first-person copy', () => {
      render(<MatchList status="empty" subject="other" subjectAlias="aoe2villain" />)
      expect(screen.getByRole('status')).toHaveTextContent(
        'aoe2villain has no matches in their history yet.',
      )
      expect(screen.queryByText(/No matches yet/)).not.toBeInTheDocument()
      expect(screen.queryByText(/Once you play/)).not.toBeInTheDocument()
    })

    it('still shows the first-person empty state for subject="self" (default)', () => {
      render(<MatchList status="empty" />)
      expect(screen.getByRole('status')).toHaveTextContent('No matches yet')
      expect(screen.getByRole('status')).toHaveTextContent('Once you play, they will appear here.')
    })
  })
})
