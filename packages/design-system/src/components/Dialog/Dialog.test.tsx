import { render, screen } from '@testing-library/react'
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
      Turning this off stops future captures.
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

  it('renders the body content between the heading and the actions', () => {
    renderDialog()
    expect(screen.getByText('Turning this off stops future captures.')).toBeInTheDocument()
  })

  it('renders a destructive primary action and a secondary action by default', () => {
    renderDialog()
    expect(screen.getByRole('button', { name: 'Turn it off' }).className).toMatch(/\btext-danger\b/)
    expect(screen.getByRole('button', { name: 'Keep it on' }).className).not.toMatch(
      /\btext-danger\b/,
    )
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
})
