import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Text } from './index'

describe('Text', () => {
  it('renders the display role as an <h2> by default, in type-display', () => {
    render(<Text role="display">Match history</Text>)
    const heading = screen.getByRole('heading', { level: 2, name: 'Match history' })
    expect(heading.tagName).toBe('H2')
    expect(heading).toHaveClass('type-display')
    expect(heading).toHaveClass('text-2xl')
    expect(heading).toHaveClass('font-semibold')
    expect(heading).toHaveClass('tracking-tight')
  })

  it('overrides the display element within the heading level set via `as`', () => {
    render(
      <Text role="display" as="h1">
        Page title
      </Text>,
    )
    const heading = screen.getByRole('heading', { level: 1, name: 'Page title' })
    expect(heading.tagName).toBe('H1')
    // The size step does not change with the level — one size per role (§8).
    expect(heading).toHaveClass('text-2xl')
  })

  it('renders body as a <p> in type-body at text-md', () => {
    render(<Text role="body">Every match this profile has played.</Text>)
    const paragraph = screen.getByText('Every match this profile has played.')
    expect(paragraph.tagName).toBe('P')
    expect(paragraph).toHaveClass('type-body')
    expect(paragraph).toHaveClass('text-md')
  })

  it('renders supporting as a <p> in type-supporting at text-sm', () => {
    render(<Text role="supporting">Most recent first.</Text>)
    const paragraph = screen.getByText('Most recent first.')
    expect(paragraph.tagName).toBe('P')
    expect(paragraph).toHaveClass('type-supporting')
    expect(paragraph).toHaveClass('text-sm')
  })

  it('renders numeric as a <span> in type-numeric, distinct from machine and identifier', () => {
    render(
      <>
        <Text role="numeric">1204</Text>
        <Text role="machine">upload_failed</Text>
        <Text role="identifier">1807091</Text>
      </>,
    )
    const numeric = screen.getByText('1204')
    const machine = screen.getByText('upload_failed')
    const identifier = screen.getByText('1807091')
    expect(numeric.tagName).toBe('SPAN')
    expect(numeric).toHaveClass('type-numeric')
    expect(machine).toHaveClass('type-machine')
    expect(identifier).toHaveClass('type-identifier')
    // The split DS-8 existed to make: three roles, three distinguishable class sets.
    expect(numeric.className).not.toBe(machine.className)
    expect(machine.className).not.toBe(identifier.className)
  })

  it('gives identifier no separate text-secondary class — type-identifier carries the colour by contract', () => {
    render(<Text role="identifier">unresolved</Text>)
    const identifier = screen.getByText('unresolved')
    expect(identifier).not.toHaveClass('text-text-secondary')
    expect(identifier).not.toHaveClass('text-text-primary')
  })

  it('every other role paints text-primary', () => {
    render(<Text role="body">primary ink</Text>)
    expect(screen.getByText('primary ink')).toHaveClass('text-text-primary')
  })

  it('renders nothing at all — not an empty element — when there are no children', () => {
    const { container } = render(<Text role="body">{''}</Text>)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when children is null or undefined', () => {
    const { container: nullContainer } = render(<Text role="body">{null}</Text>)
    expect(nullContainer).toBeEmptyDOMElement()
    const { container: undefinedContainer } = render(<Text role="body">{undefined}</Text>)
    expect(undefinedContainer).toBeEmptyDOMElement()
  })

  it('carries the standard focus-visible ring utilities, for a caller-assigned tabIndex', () => {
    render(
      <Text role="display" as="h3" tabIndex={-1}>
        Announced heading
      </Text>,
    )
    const heading = screen.getByRole('heading', { level: 3 })
    expect(heading).toHaveClass('focus-visible:outline-focus-ring')
    expect(heading).toHaveAttribute('tabindex', '-1')
  })

  it('forwards ordinary HTML attributes such as id', () => {
    render(
      <Text role="supporting" id="hint">
        A hint
      </Text>,
    )
    expect(screen.getByText('A hint')).toHaveAttribute('id', 'hint')
  })
})
