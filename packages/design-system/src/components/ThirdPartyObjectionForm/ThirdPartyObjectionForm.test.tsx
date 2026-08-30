import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ThirdPartyObjectionForm } from './index'

describe('ThirdPartyObjectionForm — order and self-containment', () => {
  it('renders the explanation above the form, and exactly one input field', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    const heading = screen.getByRole('heading', { name: 'Object to what is held about you' })
    const input = screen.getByLabelText('Your Age of Empires II profile id')
    expect(heading.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByRole('textbox')).toHaveLength(1)
  })

  it('has no signed-in chrome and no other field (name, email, message)', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/message/i)).not.toBeInTheDocument()
    // No account menu, avatar or nav — nothing that assumes a session (§10). The one "profile"
    // wording on screen is the field's own label ("your profile id"), which is expected copy.
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign out/i })).not.toBeInTheDocument()
  })

  it('lists nobody: no profile, alias or search result is rendered', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})

describe('ThirdPartyObjectionForm — load-bearing wording', () => {
  it('states "legitimate interest" and "Art. 6-1-f" in the explanation', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/legitimate interest/i)
    expect(text).toMatch(/Art\. 6-1-f/)
  })

  it('states "30 days"', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    expect(document.body.textContent).toMatch(/30 days/)
  })

  it('uses "pseudonymisation"/"pseudonymous" and never "anonymous"/"anonymised"', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/pseudonymisation|pseudonymous/)
    expect(text.toLowerCase()).not.toContain('anonymous')
    expect(text.toLowerCase()).not.toContain('anonymised')
  })

  it('links to the full privacy notice', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    expect(screen.getByRole('link', { name: 'privacy notice' })).toHaveAttribute(
      'href',
      '/privacy-notice',
    )
  })

  it('the recorded frame says "recorded" and that nothing has changed yet, with no email promise', async () => {
    const user = userEvent.setup()
    render(
      <ThirdPartyObjectionForm
        onSubmit={() => Promise.resolve()}
        privacyNoticeHref="/privacy-notice"
      />,
    )
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '12345')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    await waitFor(() =>
      expect(screen.getByText('Your objection has been recorded.')).toBeInTheDocument(),
    )
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/Nothing has been changed yet/)
    expect(text.toLowerCase()).not.toMatch(
      /we'll email you|check your inbox|we'll confirm by email/,
    )
  })
})

describe('ThirdPartyObjectionForm — states', () => {
  it('idle: the submit button is enabled — never rendered disabled', () => {
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    expect(screen.getByRole('button', { name: 'Record my objection' })).toBeEnabled()
  })

  it('validates on submit rather than disabling the button: an empty field shows FieldError and moves focus there', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<ThirdPartyObjectionForm onSubmit={onSubmit} privacyNoticeHref="/privacy-notice" />)

    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    expect(screen.getByText('Enter your numeric profile id — just the number.')).toBeInTheDocument()
    expect(screen.getByLabelText('Your Age of Empires II profile id')).toHaveFocus()
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.queryByText(/recorded/i)).not.toBeInTheDocument()
  })

  it('a non-numeric value also shows FieldError', async () => {
    const user = userEvent.setup()
    render(<ThirdPartyObjectionForm onSubmit={vi.fn()} privacyNoticeHref="/privacy-notice" />)
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), 'abc')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))
    expect(screen.getByText('Enter your numeric profile id — just the number.')).toBeInTheDocument()
  })

  it('submitting: shows the loading label and a busy button', async () => {
    let resolveSubmit: () => void = () => {}
    const onSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve
        }),
    )
    const user = userEvent.setup()
    render(<ThirdPartyObjectionForm onSubmit={onSubmit} privacyNoticeHref="/privacy-notice" />)
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '999')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    expect(screen.getByRole('button', { name: 'Recording your objection…' })).toBeDisabled()
    expect(screen.getByLabelText('Your Age of Empires II profile id')).toHaveAttribute('readonly')
    resolveSubmit()
    await waitFor(() => expect(screen.getByText(/recorded/i)).toBeInTheDocument())
  })

  it('rate-limited: a warning callout appears, and the button is present', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(Object.assign(new Error('rl'), { status: 429 }))
    render(<ThirdPartyObjectionForm onSubmit={onSubmit} privacyNoticeHref="/privacy-notice" />)
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '1')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    await waitFor(() =>
      expect(screen.getByText('Too many objections right now.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Record my objection' })).toBeInTheDocument()
  })

  it('failed: a danger callout states nothing was recorded, button enabled again', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('network'))
    render(<ThirdPartyObjectionForm onSubmit={onSubmit} privacyNoticeHref="/privacy-notice" />)
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '1')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    await waitFor(() =>
      expect(screen.getByText('We could not record your objection.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Record my objection' })).toBeEnabled()
  })

  it('calls onSubmit with the numeric profile id', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<ThirdPartyObjectionForm onSubmit={onSubmit} privacyNoticeHref="/privacy-notice" />)
    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '42')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(42))
  })
})
