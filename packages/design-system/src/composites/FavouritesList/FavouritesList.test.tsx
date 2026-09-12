import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { FavouriteEntryData } from './index'
import { FavouritesList } from './index'

const entries: FavouriteEntryData[] = [
  {
    profileId: '1',
    href: '/players/1',
    alias: 'GL.TheViper',
    clan: 'GL',
    country: 'France',
    standing: { label: 'Rating', value: '2450', unit: '#3' },
  },
  {
    profileId: '2',
    href: '/players/2',
    alias: 'Hera',
    country: 'Israel',
    standing: { status: 'empty', label: 'Rating', secondaryLine: 'Not ranked yet' },
  },
]

describe('FavouritesList', () => {
  it('always renders the "Favourites" heading, in every state', () => {
    render(<FavouritesList entries={entries} />)
    // `<h2>`, not `<h1>`: `FavouritesContainer.tsx` composes this inside `Page`, which owns the
    // route's own hidden `<h1>` (005, structural retrofit, T558).
    expect(screen.getByRole('heading', { name: 'Favourites', level: 2 })).toBeInTheDocument()
  })

  describe('default', () => {
    it('renders one row per entry, newest-favourited first as given', () => {
      render(<FavouritesList entries={entries} />)
      const rows = screen.getAllByRole('listitem')
      expect(rows).toHaveLength(2)
      expect(within(rows[0]).getByText('GL.TheViper')).toBeInTheDocument()
      expect(within(rows[1]).getByText('Hera')).toBeInTheDocument()
    })

    it('each entry links to its profile in one step and shows a remove control (FR-014, FR-013)', () => {
      render(<FavouritesList entries={entries} />)
      const rows = screen.getAllByRole('listitem')
      const firstRow = within(rows[0])
      expect(firstRow.getByRole('link')).toHaveAttribute('href', '/players/1')
      expect(firstRow.getByRole('button', { name: 'Remove from favourites' })).toBeInTheDocument()
    })

    it('has exactly two focus stops per row, link then remove button, never nested', () => {
      render(<FavouritesList entries={[entries[0]]} />)
      const row = screen.getAllByRole('listitem')[0]
      const link = within(row).getByRole('link')
      const button = within(row).getByRole('button')
      expect(link.contains(button)).toBe(false)
      expect(button.contains(link)).toBe(false)
    })

    // T560 (FR-038): favourites-list.md §5 groups "hover / focus-visible / active" as one rule for
    // `ProfileLink` — a keyboard Enter triggers `:active` with no pointer ever hovering, so the
    // link's press feedback must not depend on the hover fill alone.
    it("paints ProfileLink's active fill the same as its hover fill", () => {
      render(<FavouritesList entries={[entries[0]]} />)
      const row = screen.getAllByRole('listitem')[0]
      const link = within(row).getByRole('link')
      expect(link.className).toMatch(/\bhover:bg-surface-sunken\b/)
      expect(link.className).toMatch(/\bactive:bg-surface-sunken\b/)
    })

    // T591 (FR-037): the fill and the inline-start rule alone were still indistinguishable from
    // hover to the visual suite at this row's size (story-baseline-duplicates-debt.json) — press
    // now additionally draws a full inset `ring`, never an `outline` (an `active:outline-*` utility
    // never paints on an element that also carries `focus-visible:outline-*`, `Button/index.tsx`'s
    // own comment — a `ring`, box-shadow-based, coexists with it instead).
    it("adds a full inset boundary ring to ProfileLink's active state, never an outline", () => {
      render(<FavouritesList entries={[entries[0]]} />)
      const row = screen.getAllByRole('listitem')[0]
      const link = within(row).getByRole('link')
      expect(link.className).toMatch(/\bactive:ring-2\b/)
      expect(link.className).toMatch(/\bactive:ring-border-strong\b/)
      expect(link.className).not.toMatch(/\bactive:outline\b/)
    })

    it('shows a bracketed clan beside the alias when present, and none when absent', () => {
      render(<FavouritesList entries={entries} />)
      expect(screen.getByText('[GL]')).toBeInTheDocument()
      expect(screen.queryByText('[]')).not.toBeInTheDocument()
    })

    it('shows the country as text when known', () => {
      render(<FavouritesList entries={entries} />)
      expect(screen.getByText('France')).toBeInTheDocument()
      expect(screen.getByText('Israel')).toBeInTheDocument()
    })

    it("shows a never-ranked favourite's standing in secondary-coloured words, never an em dash or 0", () => {
      render(<FavouritesList entries={entries} />)
      const rows = screen.getAllByRole('listitem')
      const heraRow = within(rows[1])
      expect(heraRow.queryByText('—')).not.toBeInTheDocument()
      const reason = heraRow.getByText('Not ranked yet')
      expect(reason.className).toMatch(/text-text-secondary/)
      expect(heraRow.queryByText('0')).not.toBeInTheDocument()
    })

    it('calls onRemove with the entry profileId when its remove control is activated', async () => {
      const onRemove = vi.fn()
      const user = userEvent.setup()
      render(<FavouritesList entries={entries} onRemove={onRemove} />)

      await user.click(screen.getAllByRole('button', { name: 'Remove from favourites' })[0])

      expect(onRemove).toHaveBeenCalledExactlyOnceWith('1')
    })

    // Regression, favourites-list.md §10 bullet 2 / §6 "type-numeric for Standing's figures": the
    // rank is a figure that must align digit-for-digit with the rating, not a sans-serif unit
    // label (T531, research D7).
    it('renders the rank figure in type-numeric, not font-sans (§10 bullet 2, §6)', () => {
      render(<FavouritesList entries={entries} />)
      const rank = screen.getByText('#3')
      expect(rank).toHaveClass('type-numeric')
      expect(rank).not.toHaveClass('font-sans')
    })

    it('calls onNavigate for a profile link click, mirroring T388', async () => {
      const onNavigate = vi.fn()
      const user = userEvent.setup()
      render(<FavouritesList entries={entries} onNavigate={onNavigate} />)

      await user.click(screen.getAllByRole('link')[0])

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/players/1')
    })

    it('keeps every <dl> valid for an unrefreshable standing composing StatValue with a secondaryLine (axe definition-list)', () => {
      // T559 (a11y-allowlist "favourites-list"/"definition-list"): the root cause lived in
      // `StatValue` itself, not here — this component only inherited it by composing `StatValue`
      // with `secondaryLine` for a standing that could not refresh (§4). The `neverRanked` fixture
      // above does not exercise this: its `status: 'empty'` reuses `secondaryLine` as the value
      // slot's own words rather than rendering it as a second `<dl>` element at all (`StatValue`'s
      // own rule) — only a `default`-status standing with a `secondaryLine` renders the shape that
      // used to violate `<dl>`'s allowed-children rule. Fixed once, in `StatValue`; this is the
      // permanent guard that this composition specifically stays clean.
      const staleStanding: FavouriteEntryData = {
        profileId: '3',
        href: '/players/3',
        alias: 'DauT',
        country: 'Israel',
        standing: {
          label: 'Rating',
          value: '2380',
          unit: '#9',
          secondaryLine: 'Measured 12 Aug 2026 · could not refresh',
        },
      }
      const { container } = render(<FavouritesList entries={[staleStanding]} />)
      const dls = container.querySelectorAll('dl')
      expect(dls.length).toBeGreaterThan(0)
      for (const dl of dls) {
        const directChildTags = Array.from(dl.children).map((el) => el.tagName)
        expect(directChildTags).toEqual(['DT', 'DD'])
      }
    })
  })

  describe('loading', () => {
    it('shows skeleton rows and no favourite content, still under the Favourites heading', () => {
      render(<FavouritesList loading entries={entries} loadingRowCount={2} />)
      expect(screen.getByRole('heading', { name: 'Favourites' })).toBeInTheDocument()
      expect(screen.queryByText('GL.TheViper')).not.toBeInTheDocument()
      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })

    it('announces loading once for the whole list, not once per skeleton row (FR-054)', () => {
      vi.useFakeTimers()
      const { container } = render(<FavouritesList loading entries={entries} loadingRowCount={3} />)
      act(() => vi.advanceTimersByTime(200))
      vi.useRealTimers()

      expect(screen.getByRole('list')).toHaveAttribute('aria-busy', 'true')
      // Three skeleton rows, none carrying its own `aria-busy` — the list above is the one region.
      const hiddenBlocks = container.querySelectorAll('[aria-hidden="true"]')
      expect(hiddenBlocks).toHaveLength(3)
      for (const block of hiddenBlocks) {
        expect(block).not.toHaveAttribute('aria-busy')
      }
      expect(container.querySelectorAll('[aria-busy]')).toHaveLength(1)
    })
  })

  describe('error (§5)', () => {
    it('shows a danger callout with a retry, distinct from the empty state', () => {
      render(<FavouritesList error onRetry={vi.fn()} />)
      expect(screen.getByText('We could not load your favourites. Try again.')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('calls onRetry when the retry action is activated', async () => {
      const onRetry = vi.fn()
      const user = userEvent.setup()
      render(<FavouritesList error onRetry={onRetry} />)

      await user.click(screen.getByRole('button', { name: 'Try again' }))

      expect(onRetry).toHaveBeenCalledOnce()
    })
  })

  describe('empty (§5)', () => {
    it('shows an info callout naming the exact way to add a favourite, never a danger tone', () => {
      render(<FavouritesList entries={[]} />)
      expect(screen.getByText('You have not added any favourites yet.')).toBeInTheDocument()
      expect(screen.getByRole('status')).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('signed-out (§5a, US5 scenario 5, FR-015)', () => {
    it('shows an info callout and a "Sign in" primary action, and no favourited player anywhere', () => {
      render(
        <FavouritesList
          authenticated={false}
          entries={entries}
          signInHref="/sign-in?returnTo=%2Ffavourites"
        />,
      )

      expect(screen.getByText("Sign in to see the players you've favourited.")).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
        'href',
        '/sign-in?returnTo=%2Ffavourites',
      )
      expect(screen.queryByText('GL.TheViper')).not.toBeInTheDocument()
      expect(screen.queryByText('Hera')).not.toBeInTheDocument()
    })

    it('calls onNavigate for the sign-in action, carrying the return location', async () => {
      const onNavigate = vi.fn()
      const user = userEvent.setup()
      render(
        <FavouritesList
          authenticated={false}
          signInHref="/sign-in?returnTo=%2Ffavourites"
          onNavigate={onNavigate}
        />,
      )

      await user.click(screen.getByRole('link', { name: 'Sign in' }))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/sign-in?returnTo=%2Ffavourites')
    })
  })
})
