import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ErrorState } from './index'

describe('ErrorState', () => {
  it('renders nothing when there is no heading', () => {
    const { container } = render(
      <ErrorState heading="" explanation="" recovery="none" recoveryText="" />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a heading and an explanation as real text, the explanation in the primary colour', () => {
    render(
      <ErrorState
        heading="We could not load this match history"
        explanation="Something went wrong on our side. Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'We could not load this match history' }),
    ).toBeInTheDocument()
    const explanation = screen.getByText('Something went wrong on our side. Try again.')
    expect(explanation.className).toMatch(/text-text-primary/)
    expect(explanation.className).not.toMatch(/text-danger/)
  })

  it('the heading carries the danger colour, never the explanation', () => {
    render(
      <ErrorState
        heading="We could not load this match history"
        explanation="Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'We could not load this match history' }).className,
    ).toMatch(/text-danger/)
  })

  it('renders the recovery action as a real, non-disabled control', () => {
    render(
      <ErrorState
        heading="We could not load this match history"
        explanation="Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    const action = screen.getByRole('button', { name: 'Try again' })
    expect(action).toBeInTheDocument()
    expect(action).not.toBeDisabled()
  })

  it('renders the recovery sentence, not an action, when recovery is "none"', () => {
    render(
      <ErrorState
        heading="This match's replay is gone"
        explanation="The replay left Microsoft's servers before archival could capture it."
        recovery="none"
        recoveryText="Nothing can retrieve it."
      />,
    )
    expect(screen.getByText('Nothing can retrieve it.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders technical detail as selectable text when supplied, and omits it otherwise', () => {
    const { rerender } = render(
      <ErrorState
        heading="We could not start that download"
        explanation="Try again."
        action={<button type="button">Try again</button>}
        technicalDetail="reference: replay-download-504"
      />,
    )
    expect(screen.getByText('reference: replay-download-504')).toBeInTheDocument()

    rerender(
      <ErrorState
        heading="We could not start that download"
        explanation="Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    expect(screen.queryByText(/reference:/)).not.toBeInTheDocument()
  })

  it('defaults to a level-2 heading and honours an explicit heading level', () => {
    const { rerender } = render(
      <ErrorState
        heading="We could not load this match history"
        explanation="Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()

    rerender(
      <ErrorState
        heading="We could not load this match history"
        explanation="Try again."
        action={<button type="button">Try again</button>}
        headingLevel={3}
      />,
    )
    expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument()
  })

  it('carries no role by default (a plain region, for the initial render of a failed route)', () => {
    render(
      <ErrorState
        heading="We could not load this match history"
        explanation="Try again."
        action={<button type="button">Try again</button>}
      />,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('carries role="alert" when it replaces content after an interaction', () => {
    render(
      <ErrorState
        heading="We could not update your favourites"
        explanation="Try again."
        action={<button type="button">Try again</button>}
        announce
      />,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('associates the region with its heading via aria-labelledby', () => {
    render(
      <ErrorState
        heading="We could not update your favourites"
        explanation="Try again."
        action={<button type="button">Try again</button>}
        announce
      />,
    )
    const region = screen.getByRole('alert')
    const heading = screen.getByRole('heading', { name: 'We could not update your favourites' })
    expect(region).toHaveAttribute('aria-labelledby', heading.id)
  })
})
