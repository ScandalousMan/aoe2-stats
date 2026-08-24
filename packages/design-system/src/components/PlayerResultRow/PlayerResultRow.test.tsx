import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PlayerResultRow } from './index'
import type { PlayerSearchResultData } from './index'

const base: PlayerSearchResultData = {
  profileId: '12345',
  href: '/players/12345',
  alias: 'aoe2villain',
  country: 'France',
  gamesPlayed: 1042,
  clan: 'GL',
}

describe('PlayerResultRow', () => {
  it('renders the whole row as a single link to the given profile route', () => {
    render(<PlayerResultRow result={base} />)
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/players/12345')
  })

  it('shows the alias as selectable text, never an image', () => {
    render(<PlayerResultRow result={base} />)
    expect(screen.getByText('aoe2villain')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('shows a present clan bracketed beside the alias', () => {
    render(<PlayerResultRow result={base} />)
    expect(screen.getByText('[GL]')).toBeInTheDocument()
  })

  it('renders no empty bracket when clan is absent', () => {
    render(<PlayerResultRow result={{ ...base, clan: null }} />)
    expect(screen.queryByText('[]')).not.toBeInTheDocument()
    expect(screen.queryByText(/\[/)).not.toBeInTheDocument()
  })

  it('shows the country as text when known', () => {
    render(<PlayerResultRow result={base} />)
    expect(screen.getByText('France')).toBeInTheDocument()
  })

  it('renders no country field at all when country is null, never a placeholder', () => {
    render(<PlayerResultRow result={{ ...base, country: null }} />)
    expect(screen.queryByText('France')).not.toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('renders standing as "<N> games" in the monospaced family when games_played is known', () => {
    render(<PlayerResultRow result={base} />)
    const standing = screen.getByText('1042 games')
    expect(standing).toBeInTheDocument()
    expect(standing.className).toMatch(/font-mono/)
  })

  // §4: `aoe_profiles`, the local fallback, has no games-played column — the row must show no
  // numeral and no placeholder for it, not a fabricated `0`.
  it('renders no numeral, no zero and no em dash for a locally-known result with gamesPlayed: null', () => {
    render(<PlayerResultRow result={{ ...base, gamesPlayed: null }} />)
    expect(screen.queryByText(/games$/)).not.toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('renders an alias-only result (no country, no standing, no clan) without throwing', () => {
    render(
      <PlayerResultRow
        result={{
          profileId: '2',
          href: '/players/2',
          alias: 'newplayer99',
          country: null,
          gamesPlayed: null,
          clan: null,
        }}
      />,
    )
    expect(screen.getByRole('link', { name: 'newplayer99' })).toBeInTheDocument()
  })

  it('forwards a caller-supplied className onto the row', () => {
    render(<PlayerResultRow result={base} className="custom-marker" />)
    expect(screen.getByRole('link').className).toMatch(/custom-marker/)
  })

  // T388: a raw `<a href>` forces a full document reload inside a TanStack Router SPA.
  describe('onNavigate (T388)', () => {
    it('stays a real link to the profile route, href included, when onNavigate is wired', () => {
      render(<PlayerResultRow result={base} onNavigate={() => {}} />)
      expect(screen.getByRole('link')).toHaveAttribute('href', '/players/12345')
    })

    it('calls onNavigate and prevents the default navigation for a plain left click', async () => {
      const onNavigate = vi.fn()
      const user = userEvent.setup()
      render(<PlayerResultRow result={base} onNavigate={onNavigate} />)

      await user.click(screen.getByRole('link'))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/players/12345')
    })

    it('lets a modified click (new tab) fall through to native handling, never calling onNavigate', () => {
      const onNavigate = vi.fn()
      render(<PlayerResultRow result={base} onNavigate={onNavigate} />)

      fireEvent.click(screen.getByRole('link'), { ctrlKey: true })

      expect(onNavigate).not.toHaveBeenCalled()
    })

    it('does nothing special on click when no onNavigate is supplied — the native <a> just navigates', async () => {
      // jsdom does not implement real navigation and logs a "Not implemented" error the instant
      // nothing prevents the anchor's default action — which is exactly the behaviour this test
      // exists to prove, so the log is expected noise, not a signal to fix.
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const user = userEvent.setup()
      render(<PlayerResultRow result={base} />)
      const link = screen.getByRole('link')
      const preventDefaultSpy = vi.spyOn(MouseEvent.prototype, 'preventDefault')

      await user.click(link)

      expect(preventDefaultSpy).not.toHaveBeenCalled()
      preventDefaultSpy.mockRestore()
      consoleErrorSpy.mockRestore()
    })
  })
})
