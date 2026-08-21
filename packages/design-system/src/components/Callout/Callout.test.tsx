import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Callout } from './index'

describe('Callout', () => {
  it('renders nothing when there is neither a heading nor a body', () => {
    const { container } = render(<Callout tone="info" heading="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('body text always uses the primary text colour, never the tone colour', () => {
    render(
      <Callout tone="warning" heading="Heads up">
        This body must stay primary-coloured even in the warning tone.
      </Callout>,
    )
    const body = screen.getByText(/This body must stay primary-coloured/)
    expect(body.className).toMatch(/text-text-primary/)
    expect(body.className).not.toMatch(/text-warning/)
  })

  it('uses role="alert" for danger and role="status" for the other tones', () => {
    const { rerender } = render(<Callout tone="danger" heading="Failed" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()

    rerender(<Callout tone="info" heading="Explained" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('associates the region with its heading via aria-labelledby', () => {
    render(<Callout tone="info" heading="Explained" />)
    const region = screen.getByRole('status')
    const heading = screen.getByRole('heading', { name: 'Explained' })
    expect(region).toHaveAttribute('aria-labelledby', heading.id)
  })

  it('the heading is focusable at -1 so a consumer can move focus to it on mount', () => {
    render(<Callout tone="danger" heading="Failed" />)
    expect(screen.getByRole('heading', { name: 'Failed' })).toHaveAttribute('tabindex', '-1')
  })

  it('renders actions in an action row when supplied', () => {
    render(
      <Callout tone="info" heading="Explained" actions={<button type="button">Try again</button>}>
        body
      </Callout>,
    )
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
