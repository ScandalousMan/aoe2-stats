import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Footer, affiliationNote, disclaimer } from './index'

const __dirname = dirname(fileURLToPath(import.meta.url))
const readmePath = resolve(__dirname, '../../../../../README.md')

describe('Footer — the disclaimer (footer.md §5, always present)', () => {
  it('renders the Game Content Usage Rules disclaimer and the affiliation note, with no links supplied', () => {
    render(<Footer />)
    expect(screen.getByText(disclaimer)).toBeInTheDocument()
    expect(screen.getByText(affiliationNote)).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('never omits the disclaimer, regardless of which links are supplied', () => {
    render(<Footer privacyNoticeHref="/privacy-notice" objectionHref="/object" />)
    expect(screen.getByText(disclaimer)).toBeInTheDocument()
    expect(screen.getByText(affiliationNote)).toBeInTheDocument()
  })

  // footer.md: "this component's copy is normative... A change to either copy without the
  // matching change to the other is the exact defect this component exists to prevent." Both
  // sentences must stay byte-identical to README.md's "Non-commercial" section (T098a).
  it('matches README.md verbatim — the two disclosures must never drift apart', () => {
    const readme = readFileSync(readmePath, 'utf-8')
    expect(readme).toContain(
      'aoe2-stats was created under Microsoft\'s "Game Content Usage Rules" using assets from',
    )
    expect(readme).toContain('Age of Empires II: Definitive Edition, (c) Microsoft Corporation.')
    expect(readme).toContain(affiliationNote)
  })
})

describe('Footer — LinkRow (footer.md §2, ×0..1, each entry independent)', () => {
  it('renders neither link when neither href is supplied', () => {
    render(<Footer />)
    expect(screen.queryByRole('link', { name: 'Read the privacy notice' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: 'Object to what is held about me' }),
    ).not.toBeInTheDocument()
  })

  it('renders only the privacy notice link when only its href is supplied', () => {
    render(<Footer privacyNoticeHref="/privacy-notice" />)
    expect(screen.getByRole('link', { name: 'Read the privacy notice' })).toHaveAttribute(
      'href',
      '/privacy-notice',
    )
    expect(
      screen.queryByRole('link', { name: 'Object to what is held about me' }),
    ).not.toBeInTheDocument()
  })

  it('renders only the objection link when only its href is supplied', () => {
    render(<Footer objectionHref="/object" />)
    expect(screen.getByRole('link', { name: 'Object to what is held about me' })).toHaveAttribute(
      'href',
      '/object',
    )
    expect(screen.queryByRole('link', { name: 'Read the privacy notice' })).not.toBeInTheDocument()
  })

  it('renders both links, each with its own href, when both are supplied', () => {
    render(<Footer privacyNoticeHref="/privacy-notice" objectionHref="/object" />)
    expect(screen.getByRole('link', { name: 'Read the privacy notice' })).toHaveAttribute(
      'href',
      '/privacy-notice',
    )
    expect(screen.getByRole('link', { name: 'Object to what is held about me' })).toHaveAttribute(
      'href',
      '/object',
    )
  })
})

describe('Footer — link hover/focus/active consistency (T560, FR-038)', () => {
  // footer.md §5 already documented a focus ring and a `duration.fast`/`easing.standard`
  // transition for these two links — the same treatment every other inline link in the product
  // (`ThirdPartyObjectionForm`, `AccountErasurePanel`, `PrivacyNotice`) already carries. Neither
  // was actually built, which also meant these two links had no visible focus indicator at all
  // (FR-050). A class-name match alone would not prove the ring reaches a real Tab stop, so this
  // reaches the link by keyboard first.
  it('is a real Tab stop and matches the inline-link focus, transition and active treatment', async () => {
    const user = userEvent.setup()
    render(<Footer privacyNoticeHref="/privacy-notice" objectionHref="/object" />)
    const link = screen.getByRole('link', { name: 'Read the privacy notice' })

    await user.tab()
    expect(link).toHaveFocus()

    expect(link.className).toMatch(/focus-visible:outline-2/)
    expect(link.className).toMatch(/focus-visible:outline-focus-ring/)
    expect(link.className).toMatch(/\btransition-colors\b/)
    expect(link.className).toMatch(/\bduration-120\b/)
    expect(link.className).toMatch(/\bmotion-reduce:duration-0\b/)
    expect(link.className).toMatch(/\bhover:text-link-hover\b/)
    expect(link.className).toMatch(/\bactive:text-link-hover\b/)
  })
})

describe('Footer — landmark and IP (constitution X)', () => {
  it('renders a footer landmark with contentinfo role', () => {
    render(<Footer />)
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  it('carries no game asset, icon or logo — text only', () => {
    render(<Footer privacyNoticeHref="/privacy-notice" objectionHref="/object" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.querySelector('svg')).not.toBeInTheDocument()
  })
})
