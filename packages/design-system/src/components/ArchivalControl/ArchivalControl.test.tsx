import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ArchivalControl } from './index'

const bannedPhrases = [
  "don't worry",
  'rest assured',
  'for your security',
  "we've got you covered",
  'this keeps your account safe',
  'contact us',
  "we'll do our best",
  'get in touch',
]

describe('ArchivalControl — identity statement (FR-006, unchanged by the amendment)', () => {
  it('shows all four identity statements without any interaction, regardless of state', () => {
    render(<ArchivalControl state="archiving" />)
    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(4)
  })

  it('still shows all four statements in the objected state', () => {
    render(<ArchivalControl state="objected" objectedAt="on 1 January 2026" />)
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
  })

  ;['password reset', 'email verification', 'recovery'].forEach((term) => {
    it(`negates "${term}"`, () => {
      render(<ArchivalControl />)
      expect(document.body.textContent?.toLowerCase()).toContain(term)
    })
  })

  it('contains none of the banned reassurance phrases', () => {
    render(<ArchivalControl />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    for (const phrase of bannedPhrases) {
      expect(text).not.toContain(phrase)
    }
  })

  it('the identity statements are text-primary, never text-secondary or text-disabled', () => {
    render(<ArchivalControl />)
    for (const item of screen.getAllByRole('listitem')) {
      expect(item.className).toMatch(/text-text-primary/)
    }
  })

  it('the identity statements appear before the status region in DOM order', () => {
    render(<ArchivalControl state="archiving" onObject={() => {}} />)
    const list = screen.getByRole('list')
    const status = screen.getByRole('status')
    expect(list.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('ArchivalControl — the retired gate does not resurface', () => {
  it('never renders an "unanswered"/pending tone: no Accept/Decline pair, no consent question', () => {
    render(<ArchivalControl />)
    expect(screen.queryByText(/accept/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/decline/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/not now/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('renders exactly one decision control at a time', () => {
    render(<ArchivalControl state="archiving" onObject={() => {}} />)
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('states archival is already running by default, with its legal basis', () => {
    render(<ArchivalControl state="archiving" />)
    expect(screen.getByText('Archival is on.')).toBeInTheDocument()
    expect(document.body.textContent).toMatch(/legitimate interest/i)
    expect(document.body.textContent).toMatch(/Art\. 6-1-f/)
  })

  it('never renders a dialog, focus trap or Escape-triggered action', () => {
    render(<ArchivalControl state="archiving" onObject={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('ArchivalControl — archiving, never answered', () => {
  it('shows the plain "Archival is on." heading, not a resumed acknowledgement', () => {
    render(<ArchivalControl state="archiving" onObject={() => {}} />)
    expect(screen.getByText('Archival is on.')).toBeInTheDocument()
    expect(screen.queryByText('Archival resumed.')).not.toBeInTheDocument()
  })

  it('offers a single "Object to archival" button and calls onObject', async () => {
    const user = userEvent.setup()
    const onObject = vi.fn()
    render(<ArchivalControl state="archiving" onObject={onObject} />)
    await user.click(screen.getByRole('button', { name: 'Object to archival' }))
    expect(onObject).toHaveBeenCalledTimes(1)
  })

  it('uses the success tone (a status region), not danger', () => {
    render(<ArchivalControl state="archiving" onObject={() => {}} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('ArchivalControl — archiving, explicitly resumed', () => {
  it('shows a distinct "Archival resumed." heading, not the plain default heading', () => {
    render(<ArchivalControl state="archiving" justResumed onObject={() => {}} />)
    expect(screen.getByText('Archival resumed.')).toBeInTheDocument()
    expect(screen.queryByText('Archival is on.')).not.toBeInTheDocument()
  })

  it('states the boundary: future matches captured again, past objected-window matches are not recovered', () => {
    render(<ArchivalControl state="archiving" justResumed onObject={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent(/not recovered/i)
  })

  it('still offers "Object to archival" — the switch remains the same control in both directions', () => {
    render(<ArchivalControl state="archiving" justResumed onObject={() => {}} />)
    expect(screen.getByRole('button', { name: 'Object to archival' })).toBeInTheDocument()
  })
})

describe('ArchivalControl — objected', () => {
  it('reads "Archival is off." with the recorded date, using the info tone (not danger)', () => {
    render(<ArchivalControl state="objected" objectedAt="on 1 January 2026" onResume={() => {}} />)
    const region = screen.getByRole('status')
    expect(region).toHaveTextContent('Archival is off. You objected on 1 January 2026.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('offers a single "Resume archival" button and calls onResume', async () => {
    const user = userEvent.setup()
    const onResume = vi.fn()
    render(<ArchivalControl state="objected" objectedAt="on 1 January 2026" onResume={onResume} />)
    await user.click(screen.getByRole('button', { name: 'Resume archival' }))
    expect(onResume).toHaveBeenCalledTimes(1)
  })

  it('states that match history, ratings and already-archived replays are unaffected', () => {
    render(<ArchivalControl state="objected" objectedAt="on 1 January 2026" onResume={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent(/match history and ratings still update/i)
  })

  it('is not a warning: no danger tone anywhere in the frame', () => {
    render(<ArchivalControl state="objected" objectedAt="on 1 January 2026" onResume={() => {}} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('ArchivalControl — write failed', () => {
  it('renders a danger callout and returns the switch to enabled', () => {
    render(<ArchivalControl state="archiving" writeFailed onObject={() => {}} />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not save that choice')
    expect(screen.getByRole('button', { name: 'Object to archival' })).toBeEnabled()
  })

  it('does not claim the attempted action took effect: state is unchanged', () => {
    render(<ArchivalControl state="archiving" writeFailed onObject={() => {}} />)
    expect(screen.getByText('Archival is on.')).toBeInTheDocument()
    expect(screen.queryByText(/archival is off/i)).not.toBeInTheDocument()
  })

  it('renders the same failure copy for an objected-state write failure, still not claiming success', () => {
    render(
      <ArchivalControl
        state="objected"
        objectedAt="on 1 January 2026"
        writeFailed
        onResume={() => {}}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('We could not save that choice')
    expect(screen.getByText(/Archival is off\. You objected/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resume archival' })).toBeEnabled()
  })
})

describe('ArchivalControl — submitting and unavailable', () => {
  it('while submitting, the switch disables and shows its loading label', () => {
    render(<ArchivalControl state="archiving" submitting onObject={() => {}} />)
    expect(screen.getByRole('button', { name: 'Saving your choice…' })).toBeDisabled()
  })

  it('while unavailable, the switch disables and an info callout explains nothing has changed', () => {
    render(<ArchivalControl state="archiving" unavailable onObject={() => {}} />)
    expect(screen.getByRole('button', { name: 'Object to archival' })).toBeDisabled()
    expect(screen.getByText('We can’t save your choice right now')).toBeInTheDocument()
  })
})

describe('ArchivalControl — loading', () => {
  it('skeletons the status region without skeletoning the identity or basis statements', () => {
    render(<ArchivalControl loading />)
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
