import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { composeStories, setProjectAnnotations } from '@storybook/react'
import preview from '../../../.storybook/preview'
import { AccountErasurePanel, ErasedScreen } from './index'
import * as AccountErasurePanelStories from './AccountErasurePanel.stories'

// Same portable-stories setup as `Field.test.tsx` and `SiteHeader.test.tsx`.
setProjectAnnotations([preview])

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

  /** The straight path: the dialog opens with a minted token, the box is ticked, nothing has
   * expired. The erase stays pending until the test settles it. */
  async function openConfirmingDialog() {
    const user = userEvent.setup()
    const erase = deferred<void>()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok' })
    const onErase = vi.fn().mockReturnValue(erase.promise)
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={onErase} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))

    const confirm = screen.getByRole('button', { name: CONFIRM })
    act(() => confirm.focus())
    expect(confirm).toHaveFocus()
    return { user, confirm, erase, onRequestConfirmation, onErase }
  }

  const checkbox = () =>
    screen.getByRole('checkbox', { name: /I understand this cannot be undone/ })

  it('keeps focus on the confirm button from a first confirm through erasing, on the straight path', async () => {
    const { user, confirm, erase, onRequestConfirmation, onErase } = await openConfirmingDialog()

    await user.keyboard('{Enter}')
    await waitFor(() => expect(onErase).toHaveBeenCalledWith('tok'))
    expectInFlight(screen.getByRole('button', { name: /Erasing your account/ }))
    expect(screen.getByRole('button', { name: /Erasing your account/ })).toBe(confirm)

    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onErase).toHaveBeenCalledTimes(1)
    expect(onRequestConfirmation).toHaveBeenCalledTimes(1)
    expectInFlight(confirm)

    await act(async () => {
      erase.reject(new Error('server error'))
    })
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(confirm).toBeEnabled()
    expect(confirm).toHaveFocus()
  })

  it('locks the checkbox, ticked, for the whole run on the straight path, and frees it after a failure', async () => {
    const { user, erase, onErase } = await openConfirmingDialog()

    await user.keyboard('{Enter}')
    await waitFor(() => expect(onErase).toHaveBeenCalledTimes(1))
    expect(checkbox()).toBeDisabled()
    expect(checkbox()).toBeChecked()
    await user.click(checkbox())
    expect(checkbox()).toBeChecked()

    await act(async () => {
      erase.reject(new Error('server error'))
    })
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(checkbox()).toBeEnabled()
    expect(checkbox()).toBeChecked()
  })

  it('locks the checkbox, ticked, through the re-mint and the erase, and erases exactly once', async () => {
    const { user, remint, secondErase, onErase, onRequestConfirmation } = await openExpiredDialog()
    expect(checkbox()).toBeEnabled()

    await user.keyboard('{Enter}')
    await waitFor(() => expect(onRequestConfirmation).toHaveBeenCalledTimes(2))
    expect(checkbox()).toBeDisabled()
    expect(checkbox()).toBeChecked()

    // An untick during the pending re-mint changes nothing: the click and the label text both land
    // on a disabled control, and the erase the press committed still runs, once, with the new token.
    await user.click(checkbox())
    await user.click(screen.getByText('I understand this cannot be undone.'))
    expect(checkbox()).toBeChecked()

    await act(async () => {
      remint.resolve({ confirmationToken: 'fresh-token' })
    })
    await waitFor(() => expect(onErase).toHaveBeenCalledTimes(2))
    expect(onErase).toHaveBeenLastCalledWith('fresh-token')
    expect(checkbox()).toBeDisabled()
    expect(checkbox()).toBeChecked()

    await act(async () => {
      secondErase.reject(new Error('server error'))
    })
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(checkbox()).toBeEnabled()
    expect(checkbox()).toBeChecked()
    expect(onErase).toHaveBeenCalledTimes(2)
  })

  it('frees the checkbox again, still ticked, when the run ends in a second token expiry', async () => {
    const { user, remint, secondErase } = await openExpiredDialog()

    await user.keyboard('{Enter}')
    await act(async () => {
      remint.resolve({ confirmationToken: 'fresh-token' })
    })
    expect(checkbox()).toBeDisabled()
    await act(async () => {
      secondErase.reject(expired())
    })
    await waitFor(() => expect(screen.getByText('Your confirmation expired.')).toBeInTheDocument())
    expect(checkbox()).toBeEnabled()
    expect(checkbox()).toBeChecked()
  })

  // An activation that does not move focus (a programmatic click, some assistive technology)
  // leaves it on the control that held it; `fireEvent.click` models that. The run disables the checkbox and Cancel, and
  // a disabled control may not keep focus. Browsers differ in what a just-disabled focused control
  // leaves behind: WebKit and Firefox keep it as `activeElement` until the next frame, Chromium has
  // already blurred it to `body` when React's layout effect runs. jsdom does neither, so the second
  // is modelled here (React disables through `setAttribute`): the focused element is blurred first.
  const blurOnDisable = () => {
    const original = Element.prototype.setAttribute
    Element.prototype.setAttribute = function (this: Element, name: string, value: string) {
      if (name === 'disabled' && this === document.activeElement) (this as HTMLElement).blur()
      return original.call(this, name, value)
    }
    return () => {
      Element.prototype.setAttribute = original
    }
  }
  const engines = [
    ['keeping the disabled control as activeElement (WebKit, Firefox)', () => () => {}],
    ['blurring the disabled control to body (Chromium)', blurOnDisable],
  ] as const
  describe.each(engines)('in a browser %s', (_engine, model) => {
    let restore: () => void = () => {}
    beforeEach(() => {
      restore = model()
    })
    afterEach(() => restore())

    it.each([
      ['the checkbox', () => checkbox()],
      ['"Keep my account"', () => screen.getByRole('button', { name: 'Keep my account' })],
    ])(
      'moves focus from %s to the confirm button when the run starts (straight path)',
      async (_, from) => {
        const { confirm, onErase } = await openConfirmingDialog()
        act(() => from().focus())
        expect(from()).toHaveFocus()

        fireEvent.click(confirm)
        await waitFor(() => expect(onErase).toHaveBeenCalledTimes(1))
        expect(confirm).toHaveFocus()
        expect(document.body).not.toHaveFocus()
      },
    )

    it.each([
      ['the checkbox', () => checkbox()],
      ['"Keep my account"', () => screen.getByRole('button', { name: 'Keep my account' })],
    ])('moves focus from %s to the confirm button when the re-mint starts', async (_, from) => {
      const { confirm, onRequestConfirmation } = await openExpiredDialog()
      act(() => from().focus())
      expect(from()).toHaveFocus()

      fireEvent.click(confirm)
      await waitFor(() => expect(onRequestConfirmation).toHaveBeenCalledTimes(2))
      expect(confirm).toHaveFocus()
      expect(document.body).not.toHaveFocus()
    })

    // Only a control the run disables is moved: the heading is live, so a press that leaves focus
    // on it leaves it there.
    it('leaves focus on the dialog heading, a live control, when the run starts', async () => {
      const { confirm, onErase } = await openConfirmingDialog()
      const heading = screen.getByRole('heading', { name: 'This permanently erases your account' })
      act(() => heading.focus())
      expect(heading).toHaveFocus()

      fireEvent.click(confirm)
      await waitFor(() => expect(onErase).toHaveBeenCalledTimes(1))
      expect(heading).toHaveFocus()
    })
  })

  // T779 (privacy-data-rights.md §10, "The frame each `initialState` opens on"): a story's entry
  // frame is the frame its flow names. `erasing` and `confirmation-expired` are reached only through
  // a ticked box (§9), and the `Failed` story depicts a confirmed press that failed, so the three
  // open ticked; `confirming` is the frame before the box was touched. The rule is about the entry
  // frame, not about `failed`: a first mint that fails reaches it unticked (the case below).
  it.each([
    { initialState: 'failed', checked: true, locked: false },
    { initialState: 'confirmation-expired', checked: true, locked: false },
    { initialState: 'erasing', checked: true, locked: true },
    { initialState: 'confirming', checked: false, locked: false },
  ] as const)(
    'opens $initialState with the acknowledgement checked=$checked, disabled=$locked',
    ({ initialState, checked, locked }) => {
      render(<AccountErasurePanel {...noop} initialState={initialState} />)
      if (checked) expect(checkbox()).toBeChecked()
      else expect(checkbox()).not.toBeChecked()
      if (locked) expect(checkbox()).toBeDisabled()
      else expect(checkbox()).toBeEnabled()
    },
  )

  // `erasing`'s confirm is the busy `loading` button (T751), pinned by its own tests above.
  it.each(['failed', 'confirmation-expired'] as const)(
    'opens %s with the confirm button carrying none of disabled, aria-disabled, aria-busy',
    (initialState) => {
      render(<AccountErasurePanel {...noop} initialState={initialState} />)
      const confirm = screen.getByRole('button', { name: CONFIRM })
      expect(confirm).not.toHaveAttribute('disabled')
      expect(confirm).not.toHaveAttribute('aria-disabled')
      expect(confirm).not.toHaveAttribute('aria-busy')
    },
  )

  it('opens confirming with the confirm button disabled, and neither aria-disabled nor aria-busy', () => {
    render(<AccountErasurePanel {...noop} initialState="confirming" />)
    const confirm = screen.getByRole('button', { name: CONFIRM })
    expect(confirm).toHaveAttribute('disabled')
    expect(confirm).not.toHaveAttribute('aria-disabled')
    expect(confirm).not.toHaveAttribute('aria-busy')
  })

  it.each(['idle', 'minting'] as const)("opens '%s' with no dialog", (initialState) => {
    render(<AccountErasurePanel {...noop} initialState={initialState} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // Contrast case, passing before and after T779: the rule above is about a story's entry frame,
  // so `openDialog`'s catch is unchanged. A first mint that rejects opens the dialog in `failed`
  // with the box never ticked — unticked, live, confirm gated — which no `initialState` depicts.
  it('opens the dialog in failed, unticked and gated, when the first mint rejects', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockRejectedValue(new Error('mint failed'))
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() =>
      expect(screen.getByText('We could not erase your account.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(checkbox()).not.toBeChecked()
    expect(checkbox()).toBeEnabled()
    expect(screen.getByRole('button', { name: CONFIRM })).toHaveAttribute('disabled')
  })

  it('keeps the native disabled on the confirm button only while the acknowledgement is unchecked', async () => {
    const user = userEvent.setup()
    const onRequestConfirmation = vi.fn().mockResolvedValue({ confirmationToken: 'tok' })
    render(<AccountErasurePanel onRequestConfirmation={onRequestConfirmation} onErase={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    const confirm = screen.getByRole('button', { name: CONFIRM })
    expect(confirm).toHaveAttribute('disabled')
    expect(confirm).not.toHaveAttribute('aria-disabled')
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

// T779: the 20 px acknowledgement box is far under the visual comparator's tolerance
// (`maxDiffPixelRatio` 0.01), so no story baseline guards its tick. These render the real stories,
// the same composed render Storybook runs, and assert the entry frame each one depicts.
describe('AccountErasurePanel stories — the acknowledgement each opens with (T779)', () => {
  const { Failed, ConfirmationExpired, Erasing, Confirming } = composeStories(
    AccountErasurePanelStories,
  )
  const CONFIRM = 'Erase my account permanently'
  const checkbox = () =>
    screen.getByRole('checkbox', { name: /I understand this cannot be undone/ })

  it.each([
    ['Failed', Failed],
    ['ConfirmationExpired', ConfirmationExpired],
  ])('%s opens ticked and live with the confirm button enabled', (_name, Story) => {
    render(<Story />)
    expect(checkbox()).toBeChecked()
    expect(checkbox()).toBeEnabled()
    const confirm = screen.getByRole('button', { name: CONFIRM })
    expect(confirm).not.toHaveAttribute('disabled')
    expect(confirm).not.toHaveAttribute('aria-disabled')
    expect(confirm).not.toHaveAttribute('aria-busy')
  })

  it('Erasing opens ticked and locked', () => {
    render(<Erasing />)
    expect(checkbox()).toBeChecked()
    expect(checkbox()).toBeDisabled()
  })

  it('Confirming opens unticked with the confirm button disabled', () => {
    render(<Confirming />)
    expect(checkbox()).not.toBeChecked()
    expect(screen.getByRole('button', { name: CONFIRM })).toHaveAttribute('disabled')
  })
})
