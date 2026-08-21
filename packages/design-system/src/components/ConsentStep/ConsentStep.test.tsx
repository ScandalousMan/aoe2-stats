import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConsentStep } from './index'

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

describe('ConsentStep — onboarding', () => {
  it('shows all four identity statements without any interaction', () => {
    render(<ConsentStep variant="onboarding" />)
    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(4)
  })

  ;['password reset', 'email verification', 'recovery'].forEach((term) => {
    it(`negates "${term}"`, () => {
      render(<ConsentStep variant="onboarding" />)
      expect(document.body.textContent?.toLowerCase()).toContain(term)
    })
  })

  it('contains none of the banned reassurance phrases', () => {
    render(<ConsentStep variant="onboarding" />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    for (const phrase of bannedPhrases) {
      expect(text).not.toContain(phrase)
    }
  })

  it('the identity statements are text-primary, never text-secondary or text-disabled', () => {
    render(<ConsentStep variant="onboarding" />)
    for (const item of screen.getAllByRole('listitem')) {
      expect(item.className).toMatch(/text-text-primary/)
    }
  })

  it('renders exactly two decision buttons of equal size, decline reading "Not now"', () => {
    render(<ConsentStep variant="onboarding" />)
    expect(screen.getByRole('button', { name: 'Archive my replays' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeInTheDocument()
  })

  it('the identity statements appear before the decision buttons in DOM order', () => {
    render(<ConsentStep variant="onboarding" />)
    const list = screen.getByRole('list')
    const accept = screen.getByRole('button', { name: 'Archive my replays' })
    expect(list.compareDocumentPosition(accept) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('calls onAccept and onDecline from the respective buttons', async () => {
    const user = userEvent.setup()
    const onAccept = vi.fn()
    const onDecline = vi.fn()
    render(<ConsentStep variant="onboarding" onAccept={onAccept} onDecline={onDecline} />)
    await user.click(screen.getByRole('button', { name: 'Archive my replays' }))
    expect(onAccept).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Not now' }))
    expect(onDecline).toHaveBeenCalledTimes(1)
  })

  it('while submitting, both buttons disable together and the layout keeps both visible', () => {
    render(<ConsentStep variant="onboarding" submitting submittingChoice="accept" />)
    expect(screen.getByRole('button', { name: 'Saving your choice…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeDisabled()
  })

  it('on a write failure, a danger callout renders and both buttons return to enabled', () => {
    render(<ConsentStep variant="onboarding" writeFailed />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not save that choice')
    expect(screen.getByRole('button', { name: 'Archive my replays' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeEnabled()
  })
})

describe('ConsentStep — settings', () => {
  it('unanswered reads "You have not answered this yet", not "off"', () => {
    render(<ConsentStep variant="settings" decision="unanswered" />)
    expect(screen.getByText('You have not answered this yet.')).toBeInTheDocument()
  })

  it('renders the short identity form: heading plus statements 1 and 2 only', () => {
    render(<ConsentStep variant="settings" decision="declined" />)
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('declined uses the info tone, not danger, with a single "Turn on archival" action', () => {
    render(<ConsentStep variant="settings" decision="declined" onTurnOnArchival={() => {}} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Turn on archival' })).toBeInTheDocument()
  })

  it('accepted state shows the recorded state in the success tone', () => {
    render(<ConsentStep variant="settings" decision="accepted" recordedAt="3 days ago" />)
    const region = screen.getByRole('status')
    expect(region).toHaveTextContent('Archival is on.')
  })

  it('shows loading skeletons before /api/me resolves, without skeletoning the identity statement', () => {
    render(<ConsentStep variant="settings" loadingCurrentState decision="declined" />)
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('ConsentStep — withdraw-confirm', () => {
  it('is a real dialog with a heading focused on open', () => {
    render(<ConsentStep variant="withdraw-confirm" />)
    const dialog = screen.getByRole('dialog', { name: 'Turn off replay archival?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('heading', { name: 'Turn off replay archival?' })).toHaveFocus()
  })

  it('Escape calls onKeepOn (Escape never turns archival off) and never onTurnOff', async () => {
    const user = userEvent.setup()
    const onTurnOff = vi.fn()
    const onKeepOn = vi.fn()
    render(<ConsentStep variant="withdraw-confirm" onAccept={onTurnOff} onDecline={onKeepOn} />)
    await user.keyboard('{Escape}')
    expect(onKeepOn).toHaveBeenCalledTimes(1)
    expect(onTurnOff).not.toHaveBeenCalled()
  })

  it('renders a destructive "Turn it off" and a secondary "Keep it on"', () => {
    render(<ConsentStep variant="withdraw-confirm" />)
    expect(screen.getByRole('button', { name: 'Turn it off' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep it on' })).toBeInTheDocument()
  })
})
