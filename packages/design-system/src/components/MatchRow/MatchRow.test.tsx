import { readFileSync } from 'node:fs'
import path from 'node:path'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchList, MatchRow } from './index'
import type { MatchRowData, MatchRowParticipant } from './index'

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

const BRITONS_URL = '/game-assets/civilisations/britons.webp'
const ARABIA_URL = '/game-assets/maps/arabia.webp'

/** `RatingFigure` (§12.4) splits the absolute rating and the signed change across a text node and
 * a nested `<span>` so each can carry its own tone — `getByText`'s default matching only looks at
 * an element's own *direct* text nodes, never a descendant's, so the combined string is matched
 * here against `element.textContent` (which does recurse) instead of the first, direct-text-only
 * argument. */
function fullText(expected: string) {
  return (_content: string, element: Element | null) => element?.textContent === expected
}

// The opposing group's own result is left unrecorded here (`null`, "Result unknown") rather than
// `'loss'` — several fixtures below share this array with `CaptureStateBadge`'s own "Lost" label,
// and a `TeamResult` marker reading "Lost" would collide with it in the same row. The dedicated
// "Won"/"Lost"/"Result unknown" test below builds its own participants instead.
const participants: MatchRowParticipant[] = [
  { profileId: 1807091, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
  { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: null },
]

const match: MatchRowData = {
  gameId: '1001',
  href: '/matches/1001',
  outcome: 'win',
  participants,
  map: 'Arabia',
  civilisation: 'Franks',
  durationLabel: '34 min',
  playedAtRelative: '3 hours ago',
  playedAtAbsolute: '2026-08-22T09:12:00Z',
  rating: 922,
  ratingChange: { value: 12 },
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

  // match-history.md §2a: the reported production defect — an unknown result must never render
  // as "Loss", and must render as its own, differently-coloured state, not folded into either
  // resolved outcome.
  it('shows an unknown outcome as "Unknown", never as "Win" or "Loss"', () => {
    render(<MatchRow match={{ ...match, outcome: 'unknown' }} />)
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.queryByText('Win')).not.toBeInTheDocument()
    expect(screen.queryByText('Loss')).not.toBeInTheDocument()
  })

  it('does not colour the unknown outcome success or danger', () => {
    render(<MatchRow match={{ ...match, outcome: 'unknown' }} />)
    const label = screen.getByText('Unknown')
    expect(label.className).not.toContain('text-success')
    expect(label.className).not.toContain('text-danger')
    expect(label.className).toContain('text-secondary')
  })

  it('shows the map and civilisation name text when no imagery is resolved (§12.1 rule 3)', () => {
    render(<MatchRow match={match} />)
    expect(screen.getByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText('Franks')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('composes CivilisationIcon and MapThumbnail, rendering their marks when a URL resolves', () => {
    render(
      <MatchRow
        match={{
          ...match,
          civIconUrl: BRITONS_URL,
          civilisation: 'Britons',
          mapThumbnailUrl: ARABIA_URL,
        }}
      />,
    )
    const srcs = Array.from(document.querySelectorAll('img')).map((image) =>
      image.getAttribute('src'),
    )
    expect(srcs).toContain(BRITONS_URL)
    expect(srcs).toContain(ARABIA_URL)
  })

  it('shows the ladder name as a second line beneath the map name (FR-006)', () => {
    render(<MatchRow match={{ ...match, leaderboardName: '1v1 Random Map' }} />)
    expect(screen.getByText('1v1 Random Map')).toBeInTheDocument()
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

  // --- §12.4: rating and its movement -------------------------------------------------------------

  describe('rating (§12.4)', () => {
    it('renders the absolute rating with the signed change in parentheses', () => {
      render(<MatchRow match={{ ...match, rating: 922, ratingChange: { value: 16 } }} />)
      expect(screen.getByText(fullText('922 (+16)'))).toBeInTheDocument()
    })

    it('uses U+2212 MINUS SIGN, not a hyphen, for a negative change', () => {
      render(<MatchRow match={{ ...match, rating: 921, ratingChange: { value: -15 } }} />)
      expect(screen.getByText(fullText('921 (−15)'))).toBeInTheDocument()
      expect(screen.queryByText(fullText('921 (-15)'))).not.toBeInTheDocument()
    })

    it('renders a reported zero movement as "(0)" with no sign, in a neutral tone', () => {
      render(<MatchRow match={{ ...match, rating: 922, ratingChange: { value: 0 } }} />)
      const figure = screen.getByText(fullText('922 (0)'))
      expect(figure.querySelector('span')?.className).toContain('text-secondary')
      expect(figure.querySelector('span')?.className).not.toContain('text-success')
      expect(figure.querySelector('span')?.className).not.toContain('text-danger')
    })

    it('renders the rating alone, no parenthesis, when rating_diff is not known', () => {
      render(<MatchRow match={{ ...match, rating: 922, ratingChange: undefined }} />)
      expect(screen.getByText('922')).toBeInTheDocument()
      expect(screen.queryByText(/\(/)).not.toBeInTheDocument()
    })

    it('renders no rating field at all when both rating and rating_diff are absent', () => {
      render(<MatchRow match={{ ...match, rating: undefined, ratingChange: undefined }} />)
      expect(screen.queryByText(/922/)).not.toBeInTheDocument()
      expect(screen.queryByText(/\(/)).not.toBeInTheDocument()
    })
  })

  // --- §12.3: Participants, grouped by side, each in their colour --------------------------------

  describe('participants (§12.3)', () => {
    it('renders a colour swatch immediately beside every participant’s alias', () => {
      render(<MatchRow match={match} />)
      const aoe2fan = screen.getByText('aoe2fan')
      const swatch = aoe2fan.parentElement?.querySelector('[aria-hidden="true"]')
      expect(swatch).toBeInTheDocument()
      expect(
        within(aoe2fan.parentElement as HTMLElement).getByText('Colour: Yellow'),
      ).toBeInTheDocument()
    })

    it('separates two groups with the word "vs", never a glyph', () => {
      render(<MatchRow match={match} />)
      expect(screen.getByText('vs')).toBeInTheDocument()
    })

    it('caps a group at three participants and appends "and N others" — never a bare count', () => {
      const many: MatchRowParticipant[] = [
        { profileId: 1, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
        { profileId: 2, alias: 'Teammate2', teamId: 1, colorId: 2, result: 'win' },
        { profileId: 3, alias: 'Teammate3', teamId: 1, colorId: 3, result: 'win' },
        { profileId: 4, alias: 'Teammate4', teamId: 1, colorId: 5, result: 'win' },
        { profileId: 5, alias: 'aoe2villain', teamId: 2, colorId: 6, result: 'loss' },
      ]
      render(<MatchRow match={{ ...match, participants: many }} />)
      expect(screen.getByText('and 1 others')).toBeInTheDocument()
      expect(screen.queryByText(/^1 others$/)).not.toBeInTheDocument()
      expect(screen.queryByText('Teammate4')).not.toBeInTheDocument()
    })

    it('orders the viewed profile’s own group first, then the viewed profile within it', () => {
      const reordered: MatchRowParticipant[] = [
        { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'loss' },
        { profileId: 999, alias: 'SomeoneElseOnMyTeam', teamId: 1, colorId: 3, result: 'win' },
        {
          profileId: 1807091,
          alias: 'aoe2fan',
          teamId: 1,
          colorId: 4,
          result: 'win',
          isViewer: true,
        },
      ]
      render(<MatchRow match={{ ...match, participants: reordered }} />)
      const names = screen
        .getAllByText(/aoe2fan|SomeoneElseOnMyTeam|aoe2villain/)
        .map((node) => node.textContent)
      expect(names).toEqual(['aoe2fan', 'SomeoneElseOnMyTeam', 'aoe2villain'])
    })

    it('renders "Won"/"Lost"/"Result unknown" per group, never colour alone', () => {
      const wonAndLost: MatchRowParticipant[] = [
        {
          profileId: 1807091,
          alias: 'aoe2fan',
          teamId: 1,
          colorId: 4,
          result: 'win',
          isViewer: true,
        },
        { profileId: 264353, alias: 'aoe2villain', teamId: 2, colorId: 2, result: 'loss' },
      ]
      render(<MatchRow match={{ ...match, participants: wonAndLost, captureStatus: null }} />)
      expect(screen.getByText('Won')).toHaveClass('text-success')
      expect(screen.getByText('Lost')).toHaveClass('text-danger')
    })

    it('reads a group with no recorded result as "Result unknown", never as a loss', () => {
      const unresolved: MatchRowParticipant[] = participants.map((participant) => ({
        ...participant,
        result: null,
      }))
      render(<MatchRow match={{ ...match, participants: unresolved }} />)
      const markers = screen.getAllByText('Result unknown')
      expect(markers).toHaveLength(2)
      for (const marker of markers) {
        expect(marker.className).not.toContain('text-danger')
        expect(marker.className).not.toContain('text-success')
        expect(marker.className).toContain('text-secondary')
      }
    })

    it('renders no group marker at all for a mixed, should-not-occur result set', () => {
      const mixed: MatchRowParticipant[] = [
        { profileId: 1, alias: 'MixedA', teamId: 1, colorId: 1, result: 'win' },
        { profileId: 2, alias: 'MixedB', teamId: 1, colorId: 2, result: null },
        { profileId: 3, alias: 'Opponent', teamId: 2, colorId: 3, result: 'loss' },
      ]
      render(<MatchRow match={{ ...match, participants: mixed }} />)
      expect(screen.queryByText('Won')).not.toBeInTheDocument()
      expect(screen.queryByText('Result unknown')).not.toBeInTheDocument()
    })

    it('collapses a free-for-all (more than two groups) to the viewer plus "and N others", no "vs"', () => {
      const ffa: MatchRowParticipant[] = [
        { profileId: 1, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
        { profileId: 2, alias: 'Rival2', teamId: 2, colorId: 2, result: 'loss' },
        { profileId: 3, alias: 'Rival3', teamId: 3, colorId: 3, result: 'loss' },
        { profileId: 4, alias: 'Rival4', teamId: 4, colorId: 5, result: 'loss' },
      ]
      render(<MatchRow match={{ ...match, participants: ffa }} />)
      expect(screen.getByText('aoe2fan')).toBeInTheDocument()
      expect(screen.getByText('and 3 others')).toBeInTheDocument()
      expect(screen.queryByText('vs')).not.toBeInTheDocument()
      expect(screen.queryByText('Rival2')).not.toBeInTheDocument()
    })

    it('resolves an out-of-range or missing colour to the same neutral chip, never an error tone', () => {
      const neutral: MatchRowParticipant[] = [
        { profileId: 1, alias: 'aoe2fan', teamId: 1, colorId: null, result: 'win', isViewer: true },
        { profileId: 2, alias: 'aoe2villain', teamId: 2, colorId: 99, result: 'loss' },
      ]
      render(<MatchRow match={{ ...match, participants: neutral }} />)
      expect(screen.getAllByText('Colour: not recorded')).toHaveLength(2)
    })

    // §12.6: the un-projected row — every participant column NULL. The field is omitted
    // entirely, never an empty "vs" with nothing on either side.
    it('omits the Participants field entirely when participants is absent, no empty "vs"', () => {
      render(<MatchRow match={{ ...match, participants: undefined, outcome: 'unknown' }} />)
      expect(screen.queryByText('vs')).not.toBeInTheDocument()
      expect(screen.queryByText('aoe2fan')).not.toBeInTheDocument()
      expect(screen.getByText('Unknown')).toBeInTheDocument()
      // The rest of the row still renders in full — a legitimate resting state, not an error.
      expect(screen.getByText('Arabia')).toBeInTheDocument()
      expect(screen.getByText('34 min')).toBeInTheDocument()
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

  // match-history.md §2a's own reproduction: the production page this fix responds to showed
  // eight participants, none with a known result, all rendered as losses. Reproduced here at the
  // list level — every row's own outcome unrecorded — and every one MUST read "Unknown", never
  // imply anyone lost.
  it('renders an all-unknown-outcome match without implying anyone lost', () => {
    const rows: MatchRowData[] = Array.from({ length: 8 }, (_, index) => ({
      ...match,
      gameId: `unknown-${index}`,
      outcome: 'unknown' as const,
      participants: undefined,
      rating: undefined,
      ratingChange: undefined,
    }))
    render(<MatchList matches={rows} />)
    expect(screen.getAllByText('Unknown')).toHaveLength(8)
    expect(screen.queryByText('Win')).not.toBeInTheDocument()
    expect(screen.queryByText('Loss')).not.toBeInTheDocument()
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

  // §12.7: the 1280 table renames "Opponent" to "Players" and "Change" to "Rating".
  it('renders the renamed 1280 column headers "Players" and "Rating" (§12.7)', () => {
    const restore = mockMatchMediaAt(1280)
    render(<MatchList matches={[match]} />)
    expect(screen.getByRole('columnheader', { name: 'Players' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Rating' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Opponent' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Change' })).not.toBeInTheDocument()
    restore()
  })

  // §12.7: the Players column caps a side at two participants before its overflow text — the
  // column's width is bounded by the table, not by the window.
  it('caps the 1280 table Players column at two participants per side', () => {
    const restore = mockMatchMediaAt(1280)
    const many: MatchRowParticipant[] = [
      { profileId: 1, alias: 'aoe2fan', teamId: 1, colorId: 4, result: 'win', isViewer: true },
      { profileId: 2, alias: 'Teammate2', teamId: 1, colorId: 2, result: 'win' },
      { profileId: 3, alias: 'Teammate3', teamId: 1, colorId: 3, result: 'win' },
      { profileId: 4, alias: 'aoe2villain', teamId: 2, colorId: 6, result: 'loss' },
    ]
    render(<MatchList matches={[{ ...match, participants: many }]} />)
    expect(screen.getByText('and 1 others')).toBeInTheDocument()
    expect(screen.queryByText('Teammate3')).not.toBeInTheDocument()
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
