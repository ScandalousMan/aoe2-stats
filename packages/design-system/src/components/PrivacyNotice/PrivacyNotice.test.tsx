import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PrivacyNotice } from './index'

const hrefs = {
  archivalControl: '/dashboard',
  privacyRoute: '/privacy',
  objectionForm: '/object',
}

const bannedPhrases = [
  'we take your privacy seriously',
  'trusted partners',
  'as long as necessary',
  'contact support',
  'accept all cookies',
  'rest assured',
  "we've got you covered",
  'military-grade encryption',
]

describe('PrivacyNotice — the document exists and is whole', () => {
  it('renders exactly one h1 and all nine section headings', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    const h2s = screen.getAllByRole('heading', { level: 2 })
    const h2Text = h2s.map((h) => h.textContent)
    expect(h2Text).toEqual(
      expect.arrayContaining([
        'Who we are and what this is',
        'What we collect',
        'Cookies',
        'Where it is stored, and who else touches it',
        'How long we keep it',
        'Your rights, and the control that exercises each one',
        'If you are not a user of this service',
        'What we do not do',
        'How to reach us',
      ]),
    )
  })

  it('shows all eight category entries when showsAnalysisRetention is true (default)', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.getByText('Matches you ask us to analyse')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 3 }).length).toBeGreaterThanOrEqual(8)
  })

  it('shows seven category entries when showsAnalysisRetention is false, missing only the analysis one', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} showsAnalysisRetention={false} />)
    expect(screen.queryByText('Matches you ask us to analyse')).not.toBeInTheDocument()
    expect(screen.getByText('Your sign-in and your account')).toBeInTheDocument()
    expect(screen.getByText('The requests you make under this notice')).toBeInTheDocument()
  })

  it('every category entry dl carries all four non-empty labels', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const labels = ['Where it comes from', 'Why we have it', 'Legal basis', 'How long we keep it']
    for (const label of labels) {
      const matches = screen.getAllByText(label)
      expect(matches.length).toBeGreaterThanOrEqual(8)
    }
  })

  it('renders no skeleton and takes no loading prop — it is fully readable at first paint', () => {
    const { container } = render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeInTheDocument()
  })
})

describe('PrivacyNotice — legally load-bearing phrases', () => {
  it('states "legitimate interest" and "Art. 6-1-f" in the recorded-games entry', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/legitimate interest/i)
    expect(text).toMatch(/Art\. 6-1-f/)
  })

  it('states "Art. 21" and "object" in the rights section', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/Art\. 21/)
    expect(text.toLowerCase()).toContain('object')
  })

  it('contains "There is no undo" in the erasure rights item', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(document.body.textContent).toMatch(/There is no undo/)
  })

  it('uses "pseudonymous"/"pseudonymisation" and never "anonymous"/"anonymised"', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/pseudonymous|pseudonymisation/)
    expect(text.toLowerCase()).not.toContain('anonymous')
    expect(text.toLowerCase()).not.toContain('anonymised')
  })

  it('states "no password" and "no email address"', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/no password/)
    expect(text).toMatch(/no email address/)
  })

  it('states "30 days" in the non-user section', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(document.body.textContent).toMatch(/30 days/)
  })

  it('names the three processors and the three outward services, each with an EU location', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent ?? ''
    expect(text).toContain('Vercel')
    expect(text).toContain('Paris, France')
    expect(text).toContain('Neon')
    expect(text).toContain('Cloudflare')
    expect(text).toContain('worldsedgelink.com')
    expect(text).toContain('aoe.ms')
    expect(text).toContain('data.aoe2companion.com')
  })
})

describe('PrivacyNotice — the empty state (How to reach us)', () => {
  it('states no contact address is published yet when controllerContact is absent', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.getByText(/We have not published a contact address yet/)).toBeInTheDocument()
  })

  it('shows the section is never absent even without a contact', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.getByRole('heading', { name: 'How to reach us' })).toBeInTheDocument()
  })

  it('drops the "not published yet" wording once controllerContact is supplied', () => {
    render(
      <PrivacyNotice
        lastUpdated="2026-08-30"
        hrefs={hrefs}
        controllerContact={{ name: 'aoe2-stats', contactRoute: '/contact' }}
      />,
    )
    expect(screen.queryByText(/not published yet/)).not.toBeInTheDocument()
    expect(
      screen.getByText(/The controller for everything described here is aoe2-stats/),
    ).toBeInTheDocument()
  })

  it('renders no empty change-note callout when changeNote is absent', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('PrivacyNotice — tone and prohibitions', () => {
  it('contains none of the banned phrases', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    for (const phrase of bannedPhrases) {
      expect(text).not.toContain(phrase)
    }
  })
})

describe('PrivacyNotice — the objection call to action', () => {
  it('renders "Object to what is held about me" linking to hrefs.objectionForm', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const link = screen.getByRole('link', { name: 'Object to what is held about me' })
    expect(link).toHaveAttribute('href', '/object')
  })

  it('is present in the non-user section, before "What we do not do" in document order', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const link = screen.getByRole('link', { name: 'Object to what is held about me' })
    const nextHeading = screen.getByRole('heading', { name: 'What we do not do' })
    expect(
      link.compareDocumentPosition(nextHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})

describe('PrivacyNotice — contents navigation', () => {
  it('renders a nav with one in-page link per section, in document order', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const nav = screen.getByRole('navigation')
    const links = within(nav).getAllByRole('link')
    expect(links).toHaveLength(9)
    expect(links[0]).toHaveAttribute('href', '#who-we-are')
    expect(links[8]).toHaveAttribute('href', '#how-to-reach-us')
  })
})

describe('PrivacyNotice — last-updated formatting', () => {
  it('renders the date unambiguously, never DD/MM/YYYY or MM/DD/YYYY', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(
      screen.getByText(
        (_content, element) => element?.textContent === 'Last updated 30 August 2026.',
      ),
    ).toBeInTheDocument()
  })
})

describe('PrivacyNotice — the processing register link', () => {
  it('is absent when hrefs.processingRegister is not supplied', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    expect(screen.queryByText('Read the public processing register')).not.toBeInTheDocument()
  })

  it('renders when hrefs.processingRegister is supplied', () => {
    render(
      <PrivacyNotice
        lastUpdated="2026-08-30"
        hrefs={{ ...hrefs, processingRegister: '/register' }}
      />,
    )
    const link = screen.getByRole('link', { name: 'Read the public processing register' })
    expect(link).toHaveAttribute('href', '/register')
  })
})
