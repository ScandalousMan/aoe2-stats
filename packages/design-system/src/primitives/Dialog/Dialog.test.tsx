import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Dialog } from './index'

function renderDialog(overrides: Partial<Parameters<typeof Dialog>[0]> = {}) {
  const onPrimary = vi.fn()
  const onSecondary = vi.fn()
  render(
    <Dialog
      heading="Turn off replay archival?"
      primaryAction={{ label: 'Turn it off', onClick: onPrimary }}
      secondaryAction={{ label: 'Keep it on', onClick: onSecondary }}
      {...overrides}
    >
      {overrides.children ?? 'Turning this off stops future captures.'}
    </Dialog>,
  )
  return { onPrimary, onSecondary }
}

describe('Dialog', () => {
  it('is a real dialog with a heading focused on open', () => {
    renderDialog()
    const dialog = screen.getByRole('dialog', { name: 'Turn off replay archival?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('heading', { name: 'Turn off replay archival?' })).toHaveFocus()
  })

  // B5 remediation (fourth-pass adversarial review): the heading used to declare no outline class
  // at all, so Chromium's user-agent default outline painted on mount instead — visible as ~1412px
  // of `rgb(16,16,16)` plus ~707px of `rgb(255,255,255)` around the heading in the baselines, in a
  // colour that exists in no token file and contradicting this component's own spec, "the heading
  // paints no ring of its own." `outline-none` is what makes that sentence true.
  it('the heading suppresses its outline rather than painting the browser default', () => {
    renderDialog()
    const heading = screen.getByRole('heading', { name: 'Turn off replay archival?' })
    expect(heading).toHaveClass('outline-none')
  })

  it('renders the body content between the heading and the actions', () => {
    renderDialog()
    expect(screen.getByText('Turning this off stops future captures.')).toBeInTheDocument()
  })

  it('renders a destructive primary action and a secondary action by default', () => {
    renderDialog()
    expect(screen.getByRole('button', { name: 'Turn it off' })).toHaveClass('text-danger')
    expect(
      Array.from(screen.getByRole('button', { name: 'Keep it on' }).classList).filter((c) =>
        /(^|:)text-danger/.test(c),
      ),
    ).toEqual([])
  })

  it('Escape calls the secondary action and never the primary one', async () => {
    const user = userEvent.setup()
    const { onPrimary, onSecondary } = renderDialog()
    await user.keyboard('{Escape}')
    expect(onSecondary).toHaveBeenCalledTimes(1)
    expect(onPrimary).not.toHaveBeenCalled()
  })

  it('clicking the primary action calls onClick', async () => {
    const user = userEvent.setup()
    const { onPrimary } = renderDialog()
    await user.click(screen.getByRole('button', { name: 'Turn it off' }))
    expect(onPrimary).toHaveBeenCalledTimes(1)
  })

  it('traps Tab focus between the primary and secondary actions', async () => {
    const user = userEvent.setup()
    renderDialog()
    const primary = screen.getByRole('button', { name: 'Turn it off' })
    const secondary = screen.getByRole('button', { name: 'Keep it on' })
    secondary.focus()
    await user.tab()
    expect(primary).toHaveFocus()
    await user.tab({ shift: true })
    expect(secondary).toHaveFocus()
  })

  it('Shift+Tab from the heading — where focus starts on open — wraps to the last action instead of escaping the dialog', async () => {
    const user = userEvent.setup()
    renderDialog()
    const dialog = screen.getByRole('dialog', { name: 'Turn off replay archival?' })
    const heading = screen.getByRole('heading', { name: 'Turn off replay archival?' })
    const secondary = screen.getByRole('button', { name: 'Keep it on' })
    expect(heading).toHaveFocus()
    await user.tab({ shift: true })
    expect(secondary).toHaveFocus()
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
  })

  it('always calls the latest secondary action on Escape, even after a re-render', async () => {
    const user = userEvent.setup()
    const onSecondary = vi.fn()
    const { rerender } = render(
      <Dialog
        heading="Turn off replay archival?"
        primaryAction={{ label: 'Turn it off' }}
        secondaryAction={{ label: 'Keep it on', onClick: () => {} }}
      />,
    )
    rerender(
      <Dialog
        heading="Turn off replay archival?"
        primaryAction={{ label: 'Turn it off' }}
        secondaryAction={{ label: 'Keep it on', onClick: onSecondary }}
      />,
    )
    await user.keyboard('{Escape}')
    expect(onSecondary).toHaveBeenCalledTimes(1)
  })

  // T750: the keyboard handling of a dialog whose secondary action is disabled (its primary's
  // request in flight). jsdom performs no native Tab navigation, so these fire the key at the
  // focused element and assert what the handler itself did: `fireEvent` returns false when the
  // event was default-prevented, and `document.activeElement` is where the handler left focus.
  // (`user.tab()` would hide a missing `preventDefault` behind user-event's own navigation.)
  describe('keyboard handling while the secondary action is disabled', () => {
    function pressTab(from: HTMLElement, shiftKey = false) {
      return fireEvent.keyDown(from, { key: 'Tab', shiftKey })
    }

    it('forward Tab from the last enabled stop wraps to the first stop instead of leaving the dialog', () => {
      renderDialog({
        children: <input aria-label="Reason" />,
        secondaryAction: { label: 'Keep it on', disabled: true },
      })
      const primary = screen.getByRole('button', { name: 'Turn it off' })
      primary.focus()
      expect(primary).toHaveFocus()
      const notPrevented = pressTab(primary)
      expect(notPrevented).toBe(false)
      expect(screen.getByRole('textbox', { name: 'Reason' })).toHaveFocus()
    })

    it('Shift+Tab from the heading lands on the last enabled stop, not on the disabled button', () => {
      renderDialog({ secondaryAction: { label: 'Keep it on', disabled: true } })
      const heading = screen.getByRole('heading', { name: 'Turn off replay archival?' })
      expect(heading).toHaveFocus()
      const notPrevented = pressTab(heading, true)
      expect(notPrevented).toBe(false)
      expect(screen.getByRole('button', { name: 'Turn it off' })).toHaveFocus()
    })

    it('Shift+Tab from the first enabled stop wraps to the last enabled stop', () => {
      renderDialog({
        children: <input aria-label="Reason" />,
        secondaryAction: { label: 'Keep it on', disabled: true },
      })
      const input = screen.getByRole('textbox', { name: 'Reason' })
      input.focus()
      expect(pressTab(input, true)).toBe(false)
      expect(screen.getByRole('button', { name: 'Turn it off' })).toHaveFocus()
    })

    it('Escape does not call the disabled secondary action, nor the primary one', () => {
      const spy = vi.fn()
      const { onPrimary } = renderDialog({
        secondaryAction: { label: 'Keep it on', disabled: true, onClick: spy },
      })
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).not.toHaveBeenCalled()
      expect(onPrimary).not.toHaveBeenCalled()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('Escape follows the secondary action as it is re-enabled and disabled again on re-render', () => {
      const spy = vi.fn()
      const props = (disabled: boolean) => (
        <Dialog
          heading="Turn off replay archival?"
          primaryAction={{ label: 'Turn it off' }}
          secondaryAction={{ label: 'Keep it on', disabled, onClick: spy }}
        />
      )
      const { rerender } = render(props(true))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).not.toHaveBeenCalled()
      rerender(props(false))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).toHaveBeenCalledTimes(1)
      rerender(props(true))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).toHaveBeenCalledTimes(1)
    })

    it('a disabled input as the first element of the body is not a stop: Tab from the last wraps to the enabled one', () => {
      renderDialog({
        children: (
          <>
            <input aria-label="Locked" disabled />
            <input aria-label="Reason" />
          </>
        ),
      })
      const secondary = screen.getByRole('button', { name: 'Keep it on' })
      secondary.focus()
      expect(pressTab(secondary)).toBe(false)
      expect(screen.getByRole('textbox', { name: 'Reason' })).toHaveFocus()
    })
  })

  // Escape calls the secondary action only when a click on it would: a `loading` Button is
  // `aria-disabled` (a click does nothing), so Escape does nothing there either. The keydown
  // listener registers once, so `loading` is read through a ref like `disabled`.
  describe('Escape while the secondary action is loading', () => {
    function dialogWith(secondaryAction: Parameters<typeof Dialog>[0]['secondaryAction']) {
      return (
        <Dialog
          heading="Turn off replay archival?"
          primaryAction={{ label: 'Turn it off' }}
          secondaryAction={secondaryAction}
        />
      )
    }

    it('does not call a loading secondary action that is not disabled, and the dialog stays open', () => {
      const spy = vi.fn()
      render(dialogWith({ label: 'Keep it on', loading: true, onClick: spy }))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).not.toHaveBeenCalled()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('stops answering Escape when a rerender sets loading after mount', () => {
      const spy = vi.fn()
      const { rerender } = render(dialogWith({ label: 'Keep it on', onClick: spy }))
      rerender(dialogWith({ label: 'Keep it on', loading: true, onClick: spy }))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).not.toHaveBeenCalled()
    })

    it('answers Escape again, exactly once, when loading ends', () => {
      const spy = vi.fn()
      const { rerender } = render(dialogWith({ label: 'Keep it on', loading: true, onClick: spy }))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).not.toHaveBeenCalled()
      rerender(dialogWith({ label: 'Keep it on', loading: false, onClick: spy }))
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).toHaveBeenCalledTimes(1)
    })
  })

  // B1: the trap's stops are only elements that can take focus. jsdom has no layout (no
  // `checkVisibility`, empty client rects), so the unrendered cases are read from the markup:
  // `hidden`, `display: none` and `inert`.
  describe('the Tab trap counts only elements that can take focus', () => {
    function pressTab(from: HTMLElement, shiftKey = false) {
      return fireEvent.keyDown(from, { key: 'Tab', shiftKey })
    }
    const primary = () => screen.getByRole('button', { name: 'Turn it off' })
    const secondary = () => screen.getByRole('button', { name: 'Keep it on' })

    it('a hidden input before the actions is no stop: Shift+Tab from the primary wraps instead of leaving', () => {
      renderDialog({ children: <input type="hidden" name="token" defaultValue="x" /> })
      primary().focus()
      expect(pressTab(primary(), true)).toBe(false)
      expect(secondary()).toHaveFocus()
    })

    it('a hidden input is no wrap target: forward Tab from the last stop lands on a focused element', () => {
      renderDialog({ children: <input type="hidden" name="token" defaultValue="x" /> })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a textarea is a stop: Shift+Tab from a first textarea wraps to the last action', () => {
      renderDialog({ children: <textarea aria-label="Notes" /> })
      const textarea = screen.getByRole('textbox', { name: 'Notes' })
      textarea.focus()
      expect(pressTab(textarea, true)).toBe(false)
      expect(secondary()).toHaveFocus()
    })

    it('a select is a stop: forward Tab from the last action wraps to a first select', () => {
      renderDialog({
        children: (
          <select aria-label="Reason">
            <option>One</option>
          </select>
        ),
      })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(screen.getByRole('combobox', { name: 'Reason' })).toHaveFocus()
    })

    it('a button with the hidden attribute is skipped', () => {
      renderDialog({ children: <button hidden>Ghost</button> })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a button inside a hidden container is skipped', () => {
      renderDialog({
        children: (
          <div hidden>
            <button>Ghost</button>
          </div>
        ),
      })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a display: none button is skipped', () => {
      renderDialog({ children: <button style={{ display: 'none' }}>Ghost</button> })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a visibility: hidden button is skipped', () => {
      renderDialog({ children: <button style={{ visibility: 'hidden' }}>Ghost</button> })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a button inside an inert subtree is skipped', () => {
      renderDialog({
        children: (
          <div inert>
            <button>Ghost</button>
          </div>
        ),
      })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('a button inside a disabled fieldset is skipped', () => {
      renderDialog({
        children: (
          <fieldset disabled>
            <button>Ghost</button>
          </fieldset>
        ),
      })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(primary()).toHaveFocus()
    })

    it('contrast: a visible enabled input is a stop and wraps in both directions', () => {
      renderDialog({ children: <input aria-label="Reason" /> })
      const input = screen.getByRole('textbox', { name: 'Reason' })
      secondary().focus()
      expect(pressTab(secondary())).toBe(false)
      expect(input).toHaveFocus()
      expect(pressTab(input, true)).toBe(false)
      expect(secondary()).toHaveFocus()
    })
  })

  // Contrast cases for T750: these held before the fix and must keep holding.
  describe('keyboard handling that the T750 fix must not change', () => {
    it('Escape with an enabled secondary action still calls its onClick and never the primary one', () => {
      const spy = vi.fn()
      const { onPrimary } = renderDialog({
        secondaryAction: { label: 'Keep it on', disabled: false, onClick: spy },
      })
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(spy).toHaveBeenCalledTimes(1)
      expect(onPrimary).not.toHaveBeenCalled()
    })

    it('a loading primary action keeps focus and remains a Tab stop', () => {
      renderDialog({
        primaryAction: { label: 'Turn it off', loading: true, loadingLabel: 'Turning it off…' },
      })
      const primary = screen.getByRole('button', { name: 'Turning it off…' })
      expect(primary).toHaveAttribute('aria-disabled', 'true')
      expect(primary).not.toBeDisabled()
      const secondary = screen.getByRole('button', { name: 'Keep it on' })
      secondary.focus()
      // Forward Tab from the last stop wraps to the first, which is the loading primary.
      expect(fireEvent.keyDown(secondary, { key: 'Tab' })).toBe(false)
      expect(primary).toHaveFocus()
      // And backwards from it wraps to the last.
      expect(fireEvent.keyDown(primary, { key: 'Tab', shiftKey: true })).toBe(false)
      expect(secondary).toHaveFocus()
    })

    it('a disabled input between enabled stops is skipped and the trap still wraps', () => {
      renderDialog({
        children: (
          <>
            <input aria-label="Reason" />
            <input aria-label="Locked" disabled />
          </>
        ),
      })
      const secondary = screen.getByRole('button', { name: 'Keep it on' })
      secondary.focus()
      expect(fireEvent.keyDown(secondary, { key: 'Tab' })).toBe(false)
      expect(screen.getByRole('textbox', { name: 'Reason' })).toHaveFocus()
    })
  })
})
