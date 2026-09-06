import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Tooltip } from './index'

// A decorative trigger child (empty `alt`, `CountryFlag`'s own real pattern) so the tests that
// exercise `relation="label"` prove the tooltip itself supplies the name, not the child.
function FlagIcon() {
  return <img src="/flags/fr.svg" alt="" />
}

describe('Tooltip', () => {
  it('is closed by default: the content is not in the accessible tree at all', () => {
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    expect(screen.getByRole('button')).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    // It is still in the DOM, `hidden` — this is what makes the accessible name resolve without
    // ever opening (§8) — Testing Library's default queries just exclude `hidden` elements.
    expect(screen.getByRole('tooltip', { hidden: true })).toBeInTheDocument()
  })

  it('reveals the content on hover, and hides it again after unhover', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')

    await user.hover(trigger)
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent('France')

    await user.unhover(trigger)
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
  })

  it('the surface itself is hoverable: moving the pointer from the trigger onto it keeps it open', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')

    await user.hover(trigger)
    const tooltip = await screen.findByRole('tooltip')

    await user.unhover(trigger)
    await user.hover(tooltip)
    // Past the close grace period (120ms): still open because the pointer is over the surface.
    await new Promise((resolve) => setTimeout(resolve, 200))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    await user.unhover(tooltip)
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
  })

  it('reveals the content immediately on keyboard focus, and hides it on blur', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <Tooltip content="France">
          <FlagIcon />
        </Tooltip>
        <button type="button">Next stop</button>
      </div>,
    )

    await user.tab()
    const trigger = screen.getByRole('button', { name: 'France' })
    expect(trigger).toHaveFocus()
    expect(screen.getByRole('tooltip')).toHaveTextContent('France')

    await user.tab()
    expect(screen.getByRole('button', { name: 'Next stop' })).toHaveFocus()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('a mouse click that focuses the trigger does not open it by focus alone', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')
    await user.click(trigger)
    // The click pins it open (§4 active) — unpin, then a plain mouse focus must show nothing.
    await user.click(trigger)
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('Escape hides the content while leaving focus on the trigger, and it stays dismissed', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    await user.tab()
    const trigger = screen.getByRole('button', { name: 'France' })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()

    // Still dismissed while focus never left (§8's "stays dismissed" half).
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('a dismissed tooltip reopens once the pointer re-enters', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    await user.tab()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: 'France' })
    await user.hover(trigger)
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()
  })

  it('a press pins the tooltip open independently of the pointer, and a second press unpins it', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')

    await user.click(trigger)
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toBeInTheDocument()

    await user.unhover(trigger)
    // Past the hover close grace period: still open, because it is pinned, not hovered.
    await new Promise((resolve) => setTimeout(resolve, 200))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    await user.click(trigger)
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
  })

  it('a pinned tooltip stays open after the trigger blurs — pinning is independent of focus', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')

    await user.click(trigger)
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()

    trigger.blur()
    expect(trigger).not.toHaveFocus()
    // Still open: pinning is one of three independent open sources (§4 active), and blurring only
    // ends the focus one (Pinned story's round-2 fix relies on exactly this to reach a pinned-open
    // frame with no `:focus-visible` ring).
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('relation="label" (default) links the trigger to the content via aria-labelledby, matching the content id', () => {
    render(
      <Tooltip content="France">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button')
    const tooltip = screen.getByRole('tooltip', { hidden: true })
    expect(tooltip.id).toBeTruthy()
    expect(trigger).toHaveAttribute('aria-labelledby', tooltip.id)
    expect(trigger).not.toHaveAttribute('aria-describedby')
    expect(trigger).toHaveAccessibleName('France')
  })

  it('relation="describe" links the trigger to the content via aria-describedby, keeping the trigger\'s own label', () => {
    render(
      <Tooltip content="Ranked, 1v1 Random Map" relation="describe">
        Elo 1850
      </Tooltip>,
    )
    const trigger = screen.getByRole('button', { name: 'Elo 1850' })
    const tooltip = screen.getByRole('tooltip', { hidden: true })
    expect(trigger).toHaveAttribute('aria-describedby', tooltip.id)
    expect(trigger).not.toHaveAttribute('aria-labelledby')
  })

  it('a qualifier is a visually hidden prefix folded into the accessible name', () => {
    render(
      <Tooltip content="France" qualifier="Country:">
        <FlagIcon />
      </Tooltip>,
    )
    const trigger = screen.getByRole('button', { name: 'Country: France' })
    expect(trigger).toBeInTheDocument()
  })

  it('blank-after-trimming content renders the trigger child alone: no button, no tooltip node', () => {
    render(
      <Tooltip content="   ">
        <span>Just the flag</span>
      </Tooltip>,
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('tooltip', { hidden: true })).not.toBeInTheDocument()
    expect(screen.getByText('Just the flag')).toBeInTheDocument()
  })

  it('null content renders the trigger child alone, the same as blank', () => {
    render(
      <Tooltip content={null}>
        <span>Just the flag</span>
      </Tooltip>,
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('tooltip', { hidden: true })).not.toBeInTheDocument()
  })

  it('an empty-content trigger is not a tab stop', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <button type="button">Before</button>
        <Tooltip content="">
          <span>Just the flag</span>
        </Tooltip>
        <button type="button">After</button>
      </div>,
    )
    await user.tab()
    expect(screen.getByRole('button', { name: 'Before' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'After' })).toHaveFocus()
  })
})
