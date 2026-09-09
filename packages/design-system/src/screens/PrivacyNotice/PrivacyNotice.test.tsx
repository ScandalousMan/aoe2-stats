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

  // T559 (a11y-allowlist "privacy-notice"/"heading-order"): the entry, written 2026-09-05, named a
  // skip from the page's `h1` straight to the change-note `Callout`'s `h3` — a defect that no
  // longer exists as of T558 (committed before this task), which made `PrivacyNotice` compose
  // `Page` itself and downgraded its own former `<h1>` to a visible `<h2>` sitting in the header
  // between `Page`'s hidden `h1` and the change-note's `h3`. Re-derived against the code as it
  // stands today, not the entry's description: there is exactly one legitimate level-2-to-3 step
  // (the visible title to the change note), and the change note's own `h3` is a fair sub-heading of
  // that title block, not a peer of the numbered sections — so the entry's suggested fix (demoting
  // the change note to `h2`, matching every top-level section) is now moot rather than merely
  // outdated, and applying it would flatten a structure that is already correct. Confirmed with
  // axe-core directly (`heading-order`, both with and without a `changeNote`): no violation either
  // way. This is the permanent guard, walking every heading in document order.
  describe('heading order (axe heading-order)', () => {
    function headingLevels(container: HTMLElement): number[] {
      return Array.from(container.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((heading) =>
        Number(heading.tagName[1]),
      )
    }

    it('never increases by more than one step, doc-order, with a change note present', () => {
      const { container } = render(
        <PrivacyNotice
          lastUpdated="2026-08-30"
          hrefs={hrefs}
          changeNote={{
            heading: 'What changed',
            body: 'We added the objection form for non-users.',
            date: '2026-09-01',
          }}
        />,
      )
      const levels = headingLevels(container)
      expect(levels[0]).toBe(1)
      for (let i = 1; i < levels.length; i += 1) {
        expect(levels[i] - levels[i - 1]).toBeLessThanOrEqual(1)
      }
      // The one place a level-3 heading appears immediately after a level-2 one: the visible
      // title (h2) to the change note (h3) — confirming the intervening h2 the entry's stale
      // description was missing, rather than a direct h1-to-h3 skip.
      const changeNoteHeading = screen.getByRole('heading', { name: 'What changed' })
      expect(changeNoteHeading.tagName).toBe('H3')
    })

    it('never increases by more than one step, doc-order, with no change note', () => {
      const { container } = render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
      const levels = headingLevels(container)
      for (let i = 1; i < levels.length; i += 1) {
        expect(levels[i] - levels[i - 1]).toBeLessThanOrEqual(1)
      }
    })
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

// B5 remediation (fourth-pass adversarial review): every `SectionHeading`, including
// "How to reach us" (the `#how-to-reach-us` target the "Restrict processing" rights item's inline
// link points at), used to declare bare `outline-none` with no replacement — unlike `Dialog`'s and
// `Callout`'s headings, this one is a real Tab/click destination (`scrollAndFocus` moves focus here
// from a genuine `<a href="#...">` a keyboard user activates), so a reader following that link used
// to land somewhere with no visible indicator at all.
describe('PrivacyNotice — section heading focus visibility', () => {
  it('every section heading keeps the token focus ring rather than only suppressing the browser default', () => {
    render(<PrivacyNotice lastUpdated="2026-08-30" hrefs={hrefs} />)
    const heading = screen.getByRole('heading', { name: 'How to reach us' })
    expect(heading).toHaveAttribute('tabindex', '-1')
    expect(heading.className).toMatch(/\boutline-none\b/)
    expect(heading.className).toMatch(/\bfocus-visible:outline-ring\b/)
    expect(heading.className).toMatch(/\bfocus-visible:outline-offset-ring\b/)
    expect(heading.className).toMatch(/\bfocus-visible:outline-focus-ring\b/)
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
