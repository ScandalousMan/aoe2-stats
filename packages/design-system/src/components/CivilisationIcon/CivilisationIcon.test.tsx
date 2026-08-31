import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CivilisationIcon } from './index'

const BRITONS_URL = '/game-assets/civilisations/britons.webp'

describe('CivilisationIcon', () => {
  it('renders the mark and the name for a covered civilisation', () => {
    render(<CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />)
    expect(screen.getByText('Britons')).toBeInTheDocument()
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('src', BRITONS_URL)
    expect(img).toHaveAttribute('alt', '')
  })

  it('never gives the mark an accessible name — alt is always empty, decorative', () => {
    render(<CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />)
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('alt', '')
  })

  it('renders the name alone, with no img at all, for an uncovered civilisation (iconUrl undefined)', () => {
    render(<CivilisationIcon name="Gurjaras" />)
    expect(screen.getByText('Gurjaras')).toBeInTheDocument()
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('removes the mark on a failed decode, rendering identically to the uncovered case', () => {
    const { container: failedContainer } = render(
      <CivilisationIcon iconUrl="/game-assets/civilisations/does-not-exist.webp" name="Gurjaras" />,
    )
    const img = failedContainer.querySelector('img')
    expect(img).toBeInTheDocument()
    fireEvent.error(img as HTMLImageElement)
    expect(failedContainer.querySelector('img')).not.toBeInTheDocument()

    const { container: uncoveredContainer } = render(<CivilisationIcon name="Gurjaras" />)
    expect(failedContainer.textContent).toBe(uncoveredContainer.textContent)
    expect(uncoveredContainer.querySelector('img')).not.toBeInTheDocument()
  })

  it('resets the failure when a new iconUrl is supplied for a different civilisation', () => {
    const { rerender } = render(
      <CivilisationIcon iconUrl="/game-assets/civilisations/does-not-exist.webp" name="Gurjaras" />,
    )
    fireEvent.error(document.querySelector('img') as HTMLImageElement)
    expect(document.querySelector('img')).not.toBeInTheDocument()

    rerender(<CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />)
    expect(document.querySelector('img')).toHaveAttribute('src', BRITONS_URL)
  })

  it('renders "Unknown civilisation" and no mark when the name is absent entirely', () => {
    render(<CivilisationIcon iconUrl={BRITONS_URL} name={undefined} />)
    expect(screen.getByText('Unknown civilisation')).toBeInTheDocument()
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('renders "Unknown civilisation" for a blank string name too', () => {
    render(<CivilisationIcon iconUrl={BRITONS_URL} name="   " />)
    expect(screen.getByText('Unknown civilisation')).toBeInTheDocument()
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('sizes the mark from the icon-md and icon-lg tokens, never a Tailwind size utility', () => {
    const { container: mdContainer } = render(
      <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" size="md" />,
    )
    const mdImg = mdContainer.querySelector('img') as HTMLImageElement
    expect(mdImg.style.width).toBe('var(--ds-icon-md)')
    expect(mdImg.className).not.toMatch(/\bw-\d/)

    const { container: lgContainer } = render(
      <CivilisationIcon iconUrl={BRITONS_URL} name="Britons" size="lg" />,
    )
    const lgImg = lgContainer.querySelector('img') as HTMLImageElement
    expect(lgImg.style.width).toBe('var(--ds-icon-lg)')
  })

  it('is never a tab stop — the mark carries no tabindex and no title', () => {
    render(<CivilisationIcon iconUrl={BRITONS_URL} name="Britons" />)
    const img = document.querySelector('img')
    expect(img).not.toHaveAttribute('tabindex')
    expect(img).not.toHaveAttribute('title')
  })
})
