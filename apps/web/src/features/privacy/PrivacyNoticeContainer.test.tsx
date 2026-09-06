import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PrivacyNoticeContainer } from './PrivacyNoticeContainer'

// T095: `/privacy-notice` composes `PrivacyNotice` with this app's real routes as `hrefs` — no
// data fetching, no router context needed, exactly like `PrivacyNotice`'s own "no loading prop"
// rule (privacy-notice.md §5).

describe('PrivacyNoticeContainer', () => {
  it('renders with the app’s real hrefs wired in, with no provider of any kind', () => {
    render(<PrivacyNoticeContainer />)
    // Exactly one main landmark and exactly one `<h1>` (FR-022, `Page`'s own, T558) — `PrivacyNotice`
    // composes `Page` itself now, so this container renders nothing of its own around it. `Page`'s
    // title is required but visually hidden (`titleHidden`); the reader-visible "Privacy notice"
    // heading is `PrivacyNotice`'s own, downgraded to `<h2>` so it never duplicates `Page`'s `<h1>`.
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: 'Privacy notice', level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { name: 'Privacy notice', level: 2 })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Object to what is held about me' })).toHaveAttribute(
      'href',
      '/object',
    )
  })
})
