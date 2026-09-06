import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmptyState } from './index'

describe('EmptyState', () => {
  it('renders nothing when there is neither a heading nor an explanation', () => {
    const { container } = render(<EmptyState heading="" explanation="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a heading and an explanation as real text in the reading order', () => {
    render(<EmptyState heading="No matches yet" explanation="Nothing has been recorded so far." />)
    expect(screen.getByRole('heading', { name: 'No matches yet' })).toBeInTheDocument()
    expect(screen.getByText('Nothing has been recorded so far.')).toBeInTheDocument()
  })

  it('defaults to a level-2 heading and honours an explicit heading level', () => {
    const { rerender } = render(<EmptyState heading="No matches yet" explanation="Nothing yet." />)
    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()

    rerender(<EmptyState heading="No matches yet" explanation="Nothing yet." headingLevel={3} />)
    expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument()
  })

  it('renders the action as a real, non-disabled control when supplied', () => {
    render(
      <EmptyState
        heading="No favourites yet"
        explanation="Add a profile to keep it one tap away."
        action={<button type="button">Search for a profile</button>}
      />,
    )
    const action = screen.getByRole('button', { name: 'Search for a profile' })
    expect(action).toBeInTheDocument()
    expect(action).not.toBeDisabled()
  })

  it('renders no action when none is supplied', () => {
    render(<EmptyState heading="No matches yet" explanation="Nothing has been recorded so far." />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('carries no aria-live attribute — an empty state present at first paint must not announce itself', () => {
    const { container } = render(
      <EmptyState heading="No matches yet" explanation="Nothing has been recorded so far." />,
    )
    expect(container.querySelector('[aria-live]')).not.toBeInTheDocument()
  })
})
