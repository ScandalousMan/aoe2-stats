import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PrivacyNoticeContainer } from './PrivacyNoticeContainer'

// T095: `/privacy-notice` composes `PrivacyNotice` with this app's real routes as `hrefs` — no
// data fetching, no router context needed, exactly like `PrivacyNotice`'s own "no loading prop"
// rule (privacy-notice.md §5).

describe('PrivacyNoticeContainer', () => {
  it('renders with the app’s real hrefs wired in, with no provider of any kind', () => {
    render(<PrivacyNoticeContainer />)
    // Exactly one main landmark (FR-022, now `Page`'s) and one visible "Privacy notice" heading
    // in the picture — `Page`'s own title is required but visually hidden (`titleHidden`), so it
    // still names the route for a screen-reader user without duplicating what `PrivacyNotice`'s
    // own visible header already shows.
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: 'Privacy notice', level: 1 })).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Object to what is held about me' })).toHaveAttribute(
      'href',
      '/object',
    )
  })
})
