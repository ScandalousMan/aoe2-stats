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

const viewedProfile = {
  id: 'p1',
  alias: 'aoe2guy',
  country: 'France',
  profileId: '12345678',
  isPrimary: true,
}

const linkedProfiles = [
  { id: 'p1', alias: 'aoe2guy', isPrimary: true },
  { id: 'p2', alias: 'aoe2alt', isPrimary: false },
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
      country: 'Germany',
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
        '/players',
      )
      expect(screen.queryByText('rival_ace')).not.toBeInTheDocument()
    })
  })
})
