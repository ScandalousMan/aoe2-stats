import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ProfileSummary } from './index'
import type { RatingEntryData } from './index'

const entries: RatingEntryData[] = [
  {
    leaderboardId: '1v1-rm',
    leaderboardName: '1v1 Random Map',
    rating: '1842',
    ratingDelta: { value: 12 },
    rank: '#214',
    wins: 142,
    losses: 118,
    winRate: '55%',
  },
]

const FIXTURE_AVATAR_HASH = '0123456789abcdef0123456789abcdef01234567'

const viewedProfile = {
  id: 'p1',
  alias: 'aoe2guy',
  countryName: 'France',
  countryFlagUrl: '/game-assets/flags/fr.svg',
  avatarHash: FIXTURE_AVATAR_HASH,
  profileId: '12345678',
  isPrimary: true,
}

const linkedProfiles = [
  { id: 'p1', alias: 'aoe2guy', isPrimary: true },
  { id: 'p2', alias: 'aoe2alt', isPrimary: false },
]

// T457 remediation (004 spec §13.3/§13.8) — a third party's profile (no switcher, the plain
// `<span>` heading branch) with a 19-character alias, the same contrast case `aoe2guy` cannot
// exercise.
const thirdPartyLongAliasProfile = {
  id: 'p9',
  alias: 'TheUndefeatedAoE2GM',
  countryName: 'Germany',
  countryFlagUrl: '/game-assets/flags/de.svg',
  avatarHash: FIXTURE_AVATAR_HASH,
  profileId: '87654321',
  isPrimary: false,
}

const twoLeaderboardEntries: RatingEntryData[] = [
  {
    leaderboardId: '1v1-rm',
    leaderboardName: '1v1 Random Map',
    rating: '1842',
    ratingDelta: { value: 12 },
    rank: '#214',
    wins: 142,
    losses: 118,
    winRate: '55%',
    streak: 'W3',
    highestRating: '1901',
  },
  {
    leaderboardId: 'tg-rm',
    leaderboardName: 'Team Random Map',
    rating: '1690',
    ratingDelta: { value: -8 },
    rank: '#500',
    wins: 60,
    losses: 55,
    winRate: '52%',
  },
]

describe('ProfileSummary', () => {
  it('renders no leaderboard the profile has not played', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    expect(screen.getByText('1v1 Random Map')).toBeInTheDocument()
    expect(screen.queryByText('Team Random Map')).not.toBeInTheDocument()
  })

  it('renders no switcher trigger at all when unauthenticated', () => {
    render(<ProfileSummary authenticated={false} viewedProfile={viewedProfile} entries={entries} />)
    expect(screen.queryByRole('button', { name: /switch profile/ })).not.toBeInTheDocument()
    expect(screen.getByText('aoe2guy')).toBeInTheDocument()
  })

  it('the switcher trigger accessible name includes the word "profile"', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    expect(screen.getByRole('button', { name: /aoe2guy, switch profile/ })).toBeInTheDocument()
  })

  it('the open switcher shows exactly one "Primary" badge and a "Link another Steam account" item', async () => {
    const user = userEvent.setup()
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    await user.click(screen.getByRole('button', { name: /switch profile/ }))
    expect(screen.getAllByText('Primary')).toHaveLength(1)
    expect(screen.getByRole('menuitem', { name: 'Link another Steam account' })).toBeInTheDocument()
  })

  it('the switcher still renders a "Link another Steam account" item with a single linked profile', async () => {
    const user = userEvent.setup()
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={[linkedProfiles[0]]}
        entries={entries}
      />,
    )
    await user.click(screen.getByRole('button', { name: /switch profile/ }))
    expect(screen.getByRole('menuitem', { name: 'Link another Steam account' })).toBeInTheDocument()
  })

  it('shows the non-primary banner only while viewing a non-primary profile', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={{ ...viewedProfile, id: 'p2', alias: 'aoe2alt', isPrimary: false }}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    expect(
      screen.getByText('You are viewing a profile that is not your primary one.'),
    ).toBeInTheDocument()
  })

  it('does not show the non-primary banner while viewing the primary profile', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    expect(
      screen.queryByText('You are viewing a profile that is not your primary one.'),
    ).not.toBeInTheDocument()
  })

  it('every delta shows an explicit sign character', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    expect(screen.getByText('+12')).toBeInTheDocument()
  })

  it('a provisional rank shows a secondary-colour em dash while the rating still shows its real value', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={[{ ...entries[0], rank: undefined }]}
      />,
    )
    expect(screen.getByText('Not ranked yet')).toBeInTheDocument()
    expect(screen.getByText('1842')).toBeInTheDocument()
  })

  it('stale figures render at full contrast with a warning callout and an enabled retry', () => {
    const onRetry = vi.fn()
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
        status="stale"
        onRetry={onRetry}
      />,
    )
    expect(screen.getByText('1842')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('These figures could not be refreshed')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
  })

  it('never-loaded error shows a danger callout with a retry and no figures', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={[]}
        status="error"
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load your ratings')
  })

  it('empty (no rated leaderboard) still renders the identity bar with an explanatory info callout', () => {
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={[]}
      />,
    )
    expect(screen.getByText('aoe2guy')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      /Ratings appear after your first ranked match/,
    )
  })

  it('renders the Manage menu with "Unlink this profile" and calls onUnlink', async () => {
    const user = userEvent.setup()
    const onUnlink = vi.fn()
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
        onUnlink={onUnlink}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    await user.click(screen.getByRole('menuitem', { name: 'Unlink this profile' }))
    expect(onUnlink).toHaveBeenCalledTimes(1)
  })

  it('"Make primary" is absent for the primary profile\'s own Manage menu', async () => {
    const user = userEvent.setup()
    render(
      <ProfileSummary
        authenticated
        viewedProfile={viewedProfile}
        linkedProfiles={linkedProfiles}
        entries={entries}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    expect(screen.queryByRole('menuitem', { name: 'Make primary' })).not.toBeInTheDocument()
  })

  describe('subject="other" (003 spec §11)', () => {
    const thirdPartyProfile = {
      id: 'p9',
      alias: 'rival_ace',
      countryName: 'Germany',
      countryFlagUrl: '/game-assets/flags/de.svg',
      avatarHash: FIXTURE_AVATAR_HASH,
      profileId: '87654321',
      isPrimary: false,
    }

    it('renders the alias as static text, never a switcher trigger', () => {
      render(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={entries}
        />,
      )
      expect(screen.getByText('rival_ace')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /switch profile/ })).not.toBeInTheDocument()
    })

    it('renders no "Manage" menu and no non-primary banner', () => {
      render(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={entries}
        />,
      )
      expect(screen.queryByRole('button', { name: 'Manage' })).not.toBeInTheDocument()
      expect(
        screen.queryByText('You are viewing a profile that is not your primary one.'),
      ).not.toBeInTheDocument()
    })

    it('renders the favouriteToggle slot it is given, and none when none is given', () => {
      const { rerender } = render(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={entries}
          favouriteToggle={<button type="button">Add to favourites</button>}
        />,
      )
      expect(screen.getByRole('button', { name: 'Add to favourites' })).toBeInTheDocument()

      rerender(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={entries}
        />,
      )
      expect(screen.queryByRole('button', { name: 'Add to favourites' })).not.toBeInTheDocument()
    })

    it('shows AliasFreshnessNote with the profile alias and the observed date', () => {
      render(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={entries}
          aliasObservedAtLabel="12 Aug 2026"
        />,
      )
      expect(screen.getByText('Last seen as rival_ace on 12 Aug 2026.')).toBeInTheDocument()
    })

    it('never shows AliasFreshnessNote for subject="self"', () => {
      render(
        <ProfileSummary
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={entries}
          aliasObservedAtLabel="12 Aug 2026"
        />,
      )
      expect(screen.queryByText(/Last seen as/)).not.toBeInTheDocument()
    })

    it('reuses the identical never-rated info callout for a never-ranked third party', () => {
      render(
        <ProfileSummary
          subject="other"
          authenticated
          viewedProfile={thirdPartyProfile}
          entries={[]}
        />,
      )
      expect(screen.getByText('rival_ace')).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent(
        /Ratings appear after your first ranked match/,
      )
    })

    it('collapses to a single danger callout with a link back to search when not found', () => {
      render(<ProfileSummary subject="other" authenticated entries={[]} status="not-found" />)
      expect(screen.getByRole('alert')).toHaveTextContent('This player could not be found.')
      expect(screen.getByRole('link', { name: 'Back to search' })).toHaveAttribute(
        'href',
        '/search',
      )
      expect(screen.queryByText('rival_ace')).not.toBeInTheDocument()
    })

    // T388: `searchHref` used to default to `/players`, which is not a real route — only
    // `PlayerProfileContainer`'s override made the not-found callout work at all. This pins the
    // default itself, independent of any caller override.
    it('defaults searchHref to the real /search route when the caller supplies none', () => {
      render(<ProfileSummary subject="other" authenticated entries={[]} status="not-found" />)
      expect(screen.getByRole('link', { name: 'Back to search' })).toHaveAttribute(
        'href',
        '/search',
      )
    })
  })

  describe('the widened identity bar (004 spec §12)', () => {
    it('leads with the avatar, built from avatarHash', () => {
      const { container } = render(
        <ProfileSummary
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={entries}
        />,
      )
      const avatarImg = container.querySelector(
        `img[src="https://avatars.steamstatic.com/${FIXTURE_AVATAR_HASH}_full.jpg"]`,
      )
      expect(avatarImg).toBeInTheDocument()
    })

    it('renders the neutral placeholder, and no <img>, when avatarHash is absent', () => {
      const { container } = render(
        <ProfileSummary
          authenticated
          viewedProfile={{ ...viewedProfile, avatarHash: undefined }}
          linkedProfiles={linkedProfiles}
          entries={entries}
        />,
      )
      expect(container.querySelector('img[src*="steamstatic"]')).not.toBeInTheDocument()
      expect(container.querySelector('.border-border-strong')).toBeInTheDocument()
    })

    describe('Rule 1 — no alias: the id becomes the heading, never a blank one (004 FR-007)', () => {
      it('the heading reads "Player <id>" and the id appears exactly once in the frame', () => {
        render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, alias: '', profileId: '1807091' }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getByText('Player 1807091')).toBeInTheDocument()
        expect(screen.queryByText('1807091')).not.toBeInTheDocument()
      })

      it('a blank-after-trim alias triggers the same fallback as a missing one', () => {
        render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, alias: '   ', profileId: '1807091' }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getByText('Player 1807091')).toBeInTheDocument()
      })

      it('the fallback heading is font-mono, unlike a real alias', () => {
        const { container: fallback } = render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, alias: '', profileId: '1807091' }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getByText('Player 1807091')).toHaveClass('font-mono')

        const { container: named } = render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getAllByText('aoe2guy')[0]).toHaveClass('font-sans')
        expect(fallback).toBeTruthy()
        expect(named).toBeTruthy()
      })

      it('the switcher trigger accessible name uses the fallback heading', () => {
        render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, alias: '', profileId: '1807091' }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(
          screen.getByRole('button', { name: 'Player 1807091, switch profile' }),
        ).toBeInTheDocument()
      })

      it('never shows AliasFreshnessNote when there is no alias to have been observed', () => {
        render(
          <ProfileSummary
            subject="other"
            authenticated
            viewedProfile={{ ...viewedProfile, alias: '', profileId: '1807091' }}
            entries={entries}
            aliasObservedAtLabel="12 Aug 2026"
          />,
        )
        expect(screen.queryByText(/Last seen as/)).not.toBeInTheDocument()
      })
    })

    describe('Rule 2 — no country: the flag and its label are omitted cleanly (004 FR-008)', () => {
      it('renders no country name and no flag image when countryName is absent', () => {
        const { container } = render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, countryName: undefined, countryFlagUrl: undefined }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.queryByText('France')).not.toBeInTheDocument()
        expect(container.querySelector('img[src*="/game-assets/flags/"]')).not.toBeInTheDocument()
      })

      it('still renders the country name when the pack does not cover it, with no flag image', () => {
        const { container } = render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, countryName: 'Kiribati', countryFlagUrl: undefined }}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getByText('Kiribati')).toBeInTheDocument()
        expect(container.querySelector('img[src*="/game-assets/flags/"]')).not.toBeInTheDocument()
      })
    })

    // 004 spec §13 (amended FR-008, T457) — the country moved off the line and into the flag's
    // own tooltip; nothing beside the flag reads "France" any more.
    describe('§13 — the country is the flag tooltip, not adjacent text', () => {
      it("does not render the country name as visible text beside the flag; it is reachable through the flag's own tooltip", () => {
        render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        // The old adjacent text element is gone: no free-standing "France" node outside the flag
        // trigger's own (closed) tooltip content.
        expect(
          screen.queryByText('France', { selector: 'span:not([role="tooltip"])' }),
        ).not.toBeInTheDocument()
        // The name is still reachable — as the flag's accessible name — with the tooltip closed.
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Country: France' })).toBeInTheDocument()
      })
    })

    // T457 remediation (004 spec §13.3/§13.8) — the visual defect this closes is not visible in
    // jsdom (no layout), so what a unit test can prove is the CSS contract that layout depends on:
    // the name line never wraps, the alias is the element that gives up width first, and the flag
    // never does. A pixel proof of the outcome is the visual suite's job (§13.9), not this one's.
    describe('§13.3/§13.8 — the flag stays on the name line, at any alias length (T457)', () => {
      it('the name line does not wrap — the flag never gets pushed onto its own line beneath the switcher', () => {
        const { container } = render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        const nameLine = container.querySelector('.flex-nowrap')
        expect(nameLine).toBeInTheDocument()
        expect(nameLine).not.toHaveClass('flex-wrap')
      })

      it('the switcher trigger alias truncates instead of forcing the flag to wrap, for a short or a long alias', () => {
        const { unmount } = render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        expect(screen.getByText('aoe2guy')).toHaveClass('min-w-0', 'truncate')
        unmount()

        const longAlias = 'TheUndefeatedAoE2GM'
        render(
          <ProfileSummary
            authenticated
            viewedProfile={{ ...viewedProfile, alias: longAlias }}
            linkedProfiles={[{ id: 'p1', alias: longAlias, isPrimary: true }]}
            entries={entries}
          />,
        )
        expect(screen.getByText(longAlias)).toHaveClass('min-w-0', 'truncate')
      })

      it('the fallback heading (no switcher) also truncates rather than wrapping the flag beneath it', () => {
        render(
          <ProfileSummary
            subject="other"
            authenticated
            viewedProfile={thirdPartyLongAliasProfile}
            entries={entries}
          />,
        )
        expect(screen.getByText(thirdPartyLongAliasProfile.alias)).toHaveClass(
          'min-w-0',
          'truncate',
        )
      })

      it('the flag never shrinks to make room for the alias beside it', () => {
        const { container } = render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        const flagWrapper = container.querySelector('.shrink-0.text-text-secondary')
        expect(flagWrapper).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Country: France' })).toBeInTheDocument()
      })

      // Real-Chromium measurement (not jsdom, which has no layout) found that truncation on the
      // alias span alone is not sufficient: `Menu`'s own trigger wrapper is `inline-block`, which
      // blockifies as a flex item instead of becoming a flex context, so its child `<button>` is
      // never itself flex-shrunk and renders at full width regardless of the alias's own classes.
      // `Menu`'s exposed `className` prop is the only seam available without editing `Menu/
      // index.tsx` — this locks in that all five overrides it carries survive a refactor: the
      // original three (shrink-to-fit fix), plus the §13.6/§13.10 trigger padding-inline density
      // step (`px-3` below `md`, reverting to the `Button` default `px-4` from `md` up).
      it("carries the five overrides the switcher trigger's own inline-block wrapper needs to shrink and reflow", () => {
        const { container } = render(
          <ProfileSummary
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={entries}
          />,
        )
        const triggerWrapper = screen
          .getByRole('button', { name: 'aoe2guy, switch profile' })
          .closest('div')
        expect(triggerWrapper).toHaveClass(
          '!flex',
          'min-w-0',
          '[&>button]:min-w-0',
          '[&>button]:px-3',
          'md:[&>button]:px-4',
        )
        expect(container.querySelector('.flex-nowrap')).toContainElement(triggerWrapper)
      })
    })

    it('omits ProfileId while the fallback heading is in force, and shows it otherwise', () => {
      const { unmount } = render(
        <ProfileSummary
          authenticated
          viewedProfile={{ ...viewedProfile, alias: '', profileId: '1807091' }}
          linkedProfiles={linkedProfiles}
          entries={entries}
        />,
      )
      expect(screen.queryByText('1807091')).not.toBeInTheDocument()
      unmount()

      render(
        <ProfileSummary
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={entries}
        />,
      )
      expect(screen.getByText('12345678')).toBeInTheDocument()
    })

    it('a profile with no alias, no country and no avatar renders in full, and "No ratings yet" is unchanged', () => {
      const { container } = render(
        <ProfileSummary
          authenticated
          viewedProfile={{
            id: 'p1807091',
            alias: '',
            countryName: undefined,
            countryFlagUrl: undefined,
            avatarHash: undefined,
            profileId: '1807091',
            isPrimary: true,
          }}
          linkedProfiles={[{ id: 'p1807091', alias: '1807091', isPrimary: true }]}
          entries={[]}
        />,
      )
      expect(screen.getByText('Player 1807091')).toBeInTheDocument()
      expect(container.querySelector('img[src*="steamstatic"]')).not.toBeInTheDocument()
      expect(container.querySelector('img[src*="/game-assets/flags/"]')).not.toBeInTheDocument()
      // "No ratings yet" is a real and correct outcome, not a failure — the same info tone and
      // copy §5 already shipped, never a warning or danger callout.
      expect(screen.getByRole('status')).toHaveTextContent(
        /Ratings appear after your first ranked match/,
      )
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe("compact variant renders the primary leaderboard's rating and rank only, on one row (spec §3)", () => {
    it("renders the primary (first) leaderboard's rating", () => {
      render(
        <ProfileSummary
          variant="compact"
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={twoLeaderboardEntries}
        />,
      )
      expect(screen.getByText('1842')).toBeInTheDocument()
    })

    it('does not render the second leaderboard at all', () => {
      render(
        <ProfileSummary
          variant="compact"
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={twoLeaderboardEntries}
        />,
      )
      expect(screen.queryByText('Team Random Map')).not.toBeInTheDocument()
      expect(screen.queryByText('1690')).not.toBeInTheDocument()
    })

    it("renders the primary leaderboard's rank", () => {
      render(
        <ProfileSummary
          variant="compact"
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={twoLeaderboardEntries}
        />,
      )
      expect(screen.getByText('#214')).toBeInTheDocument()
    })

    it('does not render record, win rate, streak or best', () => {
      render(
        <ProfileSummary
          variant="compact"
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={twoLeaderboardEntries}
        />,
      )
      expect(screen.queryByText('142 W · 118 L')).not.toBeInTheDocument()
      expect(screen.queryByText('Record')).not.toBeInTheDocument()
      expect(screen.queryByText('55%')).not.toBeInTheDocument()
      expect(screen.queryByText('Win rate')).not.toBeInTheDocument()
      expect(screen.queryByText('W3')).not.toBeInTheDocument()
      expect(screen.queryByText('Streak')).not.toBeInTheDocument()
      expect(screen.queryByText('1901')).not.toBeInTheDocument()
      expect(screen.queryByText('Best')).not.toBeInTheDocument()
    })

    // Contrast case (same fixture data, `board` variant): pins the difference between the two
    // variants rather than only asserting the compact side in isolation.
    it('the same two entries in the default (board) variant render the second leaderboard and the full columns', () => {
      render(
        <ProfileSummary
          authenticated
          viewedProfile={viewedProfile}
          linkedProfiles={linkedProfiles}
          entries={twoLeaderboardEntries}
        />,
      )
      expect(screen.getByText('Team Random Map')).toBeInTheDocument()
      expect(screen.getByText('1690')).toBeInTheDocument()
      expect(screen.getByText('142 W · 118 L')).toBeInTheDocument()
      expect(screen.getAllByText('55%').length).toBeGreaterThan(0)
      expect(screen.getByText('W3')).toBeInTheDocument()
      expect(screen.getByText('1901')).toBeInTheDocument()
    })

    it('a compact board with no rank yet renders the existing "Not ranked yet" treatment without throwing', () => {
      expect(() =>
        render(
          <ProfileSummary
            variant="compact"
            authenticated
            viewedProfile={viewedProfile}
            linkedProfiles={linkedProfiles}
            entries={[{ ...twoLeaderboardEntries[0], rank: undefined }, twoLeaderboardEntries[1]]}
          />,
        ),
      ).not.toThrow()
      expect(screen.getByText('Not ranked yet')).toBeInTheDocument()
      expect(screen.getByText('1842')).toBeInTheDocument()
    })
  })
})
