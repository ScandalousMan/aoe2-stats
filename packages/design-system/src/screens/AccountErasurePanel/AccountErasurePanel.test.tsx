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

// T751 (privacy-data-rights.md §9, "Focus while a confirm is in flight"): the re-mint and the erase
// that follows it are one in-flight run. `ConfirmAction` is `Button`'s `loading` for all of it —
// never the native `disabled`, which would drop the focus the press left on it to `body`.
describe('AccountErasurePanel — focus while a confirm is in flight (T751)', () => {
  const CONFIRM = 'Erase my account permanently'

  function deferred<T>() {
    let resolve: (value: T) => void = () => {}
    let reject: (reason: unknown) => void = () => {}
    const promise = new Promise<T>((res, rej) => {
      resolve = res
      reject = rej
    })
    return { promise, resolve, reject }
  }

  const expired = () => Object.assign(new Error('expired'), { status: 403 })

  /** Opens the dialog, ticks the box, and lets the first `POST` end in a 403, so the dialog reads
   * `confirmation-expired`. The second mint and the second erase stay pending until the test
   * settles them. */
  async function openExpiredDialog() {
    const user = userEvent.setup()
    const remint = deferred<{ confirmationToken: string }>()
    const secondErase = deferred<void>()
    const onRequestConfirmation = vi
      .fn()
      .mockResolvedValueOnce({ confirmationToken: 'stale-token' })
      .mockReturnValueOnce(remint.promise)
    const onErase = vi
      .fn()
      .mockRejectedValueOnce(expired())
      .mockReturnValueOnce(secondErase.promise)
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={onErase} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: CONFIRM }))
    await waitFor(() => expect(screen.getByText('Your confirmation expired.')).toBeInTheDocument())

    const confirm = screen.getByRole('button', { name: CONFIRM })
    act(() => confirm.focus())
    expect(confirm).toHaveFocus()
    return { user, confirm, remint, secondErase, onRequestConfirmation, onErase }
  }

  function expectInFlight(confirm: HTMLElement) {
    expect(confirm).toHaveFocus()
    expect(confirm).not.toHaveAttribute('disabled')
    expect(confirm).toHaveAttribute('aria-busy', 'true')
    expect(confirm).toHaveAttribute('aria-disabled', 'true')
    expect(confirm).toHaveTextContent('Erasing your account…')
    expect(screen.getByRole('button', { name: 'Keep my account' })).toBeDisabled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  }

  it('keeps focus on the confirm button through the re-mint, the erase, and a failed run', async () => {
    const { user, confirm, remint, secondErase, onRequestConfirmation, onErase } =
      await openExpiredDialog()

    await user.keyboard('{Enter}')
    await waitFor(() => expect(onRequestConfirmation).toHaveBeenCalledTimes(2))

    // The re-mint is pending: the same element, busy, not disabled, the callout gone.
    expectInFlight(screen.getByRole('button', { name: /Erasing your account/ }))
    expect(screen.getByRole('button', { name: /Erasing your account/ })).toBe(confirm)
    expect(screen.queryByText('Your confirmation expired.')).not.toBeInTheDocument()

    // Escape during the re-mint calls neither action and leaves the dialog open.
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onErase).toHaveBeenCalledTimes(1)
    expect(onRequestConfirmation).toHaveBeenCalledTimes(2)
    expectInFlight(confirm)

    // The re-mint resolves and the erase starts: one run, same element, same frame.
    await act(async () => {
      remint.resolve({ confirmationToken: 'fresh-token' })
    })
    await waitFor(() => expect(onErase).toHaveBeenLastCalledWith('fresh-token'))
    expectInFlight(confirm)
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onErase).toHaveBeenCalledTimes(2)

    // The run ends in `failed`: the button is enabled again, focus still on it.
    await act(async () => {
      secondErase.reject(new Error('server error'))
    })
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: CONFIRM })).toBe(confirm)
    expect(confirm).toBeEnabled()
    expect(confirm).not.toHaveAttribute('aria-busy')
    expect(confirm).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Keep my account' })).toBeEnabled()
  })

  it('keeps focus on the confirm button when the run ends in a second token expiry', async () => {
    const { user, confirm, remint, secondErase } = await openExpiredDialog()

    await user.keyboard('{Enter}')
    expectInFlight(confirm)
    await act(async () => {
      remint.resolve({ confirmationToken: 'fresh-token' })
    })
    expectInFlight(confirm)
    await act(async () => {
      secondErase.reject(expired())
    })
    await waitFor(() => expect(screen.getByText('Your confirmation expired.')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: CONFIRM })).toBe(confirm)
    expect(confirm).toBeEnabled()
    expect(confirm).toHaveFocus()
  })

  it('keeps focus on the confirm button when the re-mint itself fails', async () => {
    const { user, confirm, remint } = await openExpiredDialog()

    await user.keyboard('{Enter}')
    expectInFlight(confirm)
    await act(async () => {
      remint.reject(new Error('mint failed'))
    })
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(confirm).toBeEnabled()
    expect(confirm).toHaveFocus()
  })

  it('keeps the native disabled on the confirm button only while the acknowledgement is unchecked', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok' })
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    const confirm = screen.getByRole('button', { name: CONFIRM })
    expect(confirm).toHaveAttribute('disabled')
    expect(confirm).not.toHaveAttribute('aria-busy')
    // Keep my account is live: nothing is in flight.
    expect(screen.getByRole('button', { name: 'Keep my account' })).toBeEnabled()
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

  // T591 (structural-tier.md §9 "hover" — "two signals, one of which is not colour"): this
  // inline link's own class copy was missing the underline-thickness half of `Link`'s `inline`
  // recipe.
  it('thickens the underline on hover and on press, matching every other inline link', () => {
    render(<ErasedScreen homeHref="/privacy-notice" />)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('decoration-1')
    expect(link).toHaveClass('hover:decoration-2')
    expect(link).toHaveClass('active:decoration-2')
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
