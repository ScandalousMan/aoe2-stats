import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AccountErasurePanel, ErasedScreen } from './index'

const noop = {
  onRequestConfirmation: () => Promise.reject(new Error('unused')),
  onErase: () => Promise.reject(new Error('unused')),
}

describe('AccountErasurePanel — the wording that is the point of the task', () => {
  it('shows "There is no undo" in the default frame, before any dialog is opened', () => {
    render(<AccountErasurePanel {...noop} />)
    expect(screen.getByText(/There is no undo/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows both consequence groups above the erase button', () => {
    render(<AccountErasurePanel {...noop} />)
    expect(screen.getByText('What is deleted, for good:')).toBeInTheDocument()
    expect(screen.getByText('What survives, and why:')).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Erase my account' })
    const deletedGroup = screen.getByText('What is deleted, for good:')
    expect(
      deletedGroup.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('uses "pseudonymisation" in the surviving-data group, and never "anonymous"/"anonymised"', () => {
    render(<AccountErasurePanel {...noop} />)
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/pseudonymisation|pseudonymous/)
    expect(text.toLowerCase()).not.toContain('anonymous')
    expect(text.toLowerCase()).not.toContain('anonymised')
  })
})

describe('AccountErasurePanel — the two-step confirmation flow', () => {
  it('opens the dialog and mints a token when the erase button is pressed', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok-1' })
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    expect(onRequestConfirmation).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Erase my account permanently' })).toBeDisabled()
  })

  it('gates the confirm action on the acknowledgement checkbox', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok-1' })
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    const confirmButton = screen.getByRole('button', { name: 'Erase my account permanently' })
    expect(confirmButton).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    expect(confirmButton).toBeEnabled()
  })

  it('calls onErase with the minted token once confirmed, and erases', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok-2' })
    const onErase = vi.fn().mockResolvedValue(undefined)
    const onErased = vi.fn()
    render(
      <AccountErasurePanel
        onRequestConfirmation={onRequestConfirmation}
        onErase={onErase}
        onErased={onErased}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))

    await waitFor(() => expect(onErase).toHaveBeenCalledWith('tok-2'))
    await waitFor(() => expect(onErased).toHaveBeenCalledTimes(1))
  })

  it('Escape calls the cancelling action, never the destructive one', async () => {
    const user = userEvent.setup()
    const onErase = vi.fn()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok-3' })
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={onErase} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(onErase).not.toHaveBeenCalled()
  })
})

describe('AccountErasurePanel — token expiry (403) silently re-mints', () => {
  it('shows the expired message and re-mints on the next confirm press, without claiming success', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi
      .fn()
      .mockResolvedValueOnce({ confirmationToken: 'stale-token' })
      .mockResolvedValueOnce({ confirmationToken: 'fresh-token' })
    const onErase = vi
      .fn()
      .mockRejectedValueOnce(Object.assign(new Error('expired'), { status: 403 }))
      .mockResolvedValueOnce(undefined)

    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={onErase} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))

    await waitFor(() => expect(screen.getByText('Your confirmation expired.')).toBeInTheDocument())
    expect(screen.queryByText(/account has been erased/i)).not.toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // The checkbox is still checked; confirming again silently re-mints, then erases with the
    // fresh token — the user simply confirms once more, per the spec's own wording.
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))
    await waitFor(() => expect(onRequestConfirmation).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(onErase).toHaveBeenLastCalledWith('fresh-token'))
  })
})

describe('AccountErasurePanel — other failure', () => {
  it('keeps the dialog open, shows the failure message, and re-enables confirm', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok-4' })
    const onErase = vi.fn().mockRejectedValue(new Error('server error'))

    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={onErase} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))

    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Erase my account permanently' })).toBeEnabled()
  })
})

describe('ErasedScreen — the terminal state', () => {
  it('states the account is erased, names what survives, and carries no "sign back in" control', () => {
    render(<ErasedScreen homeHref="/privacy-notice" />)
    expect(screen.getByText('Your account has been erased.')).toBeInTheDocument()
    expect(document.body.textContent).toMatch(/pseudonymous/)
    // The copy itself says "nothing left here to sign in to" (privacy-data-rights.md §4.4) — the
    // prohibition is on an interactive sign-in control, not on the word appearing in prose.
    expect(screen.queryByRole('link', { name: /sign/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign/i })).not.toBeInTheDocument()
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/privacy-notice')
  })
})

// Guards against a regression `act()` would otherwise mask: unmounting mid-flight must not warn
// or throw.
describe('AccountErasurePanel — unmount safety', () => {
  it('does not throw when unmounted while a request is in flight', async () => {
    let resolveConfirmation: (value: { confirmationToken: string }) => void = () => {}
    const onRequestConfirmation = vi.fn(
      () =>
        new Promise<{ confirmationToken: string }>((resolve) => {
          resolveConfirmation = resolve
        }),
    )
    const user = userEvent.setup()
    const { unmount } = render(
      <AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />,
    )
    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    unmount()
    await act(async () => {
      resolveConfirmation({ confirmationToken: 'tok' })
    })
  })
})
