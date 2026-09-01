import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CountryFlag } from './index'

const FRANCE_URL = '/game-assets/flags/fr.svg'

describe('CountryFlag', () => {
  it('renders the framed flag and the country name for a covered country', () => {
    const { container } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    expect(screen.getByText('France')).toBeInTheDocument()
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', FRANCE_URL)
    expect(img).toHaveAttribute('alt', '')
    // The frame is drawn only when an image is actually rendered inside it (§2).
    expect(container.querySelector('.border-border')).toBeInTheDocument()
  })

  it('never gives the flag an accessible name — alt is always empty, decorative', () => {
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('alt', '')
  })

  it('renders the name alone, with no img and no frame, for an uncovered country (flagUrl undefined)', () => {
    const { container } = render(<CountryFlag countryName="Kiribati" />)
    expect(screen.getByText('Kiribati')).toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('.border-border')).not.toBeInTheDocument()
  })

  it('removes the image and its frame together on a failed decode, matching the uncovered render', () => {
    const { container: failedContainer } = render(
      <CountryFlag flagUrl="/game-assets/flags/does-not-exist.svg" countryName="Kiribati" />,
    )
    const img = failedContainer.querySelector('img')
    expect(img).toBeInTheDocument()
    fireEvent.error(img as HTMLImageElement)
    expect(failedContainer.querySelector('img')).not.toBeInTheDocument()
    expect(failedContainer.querySelector('.border-border')).not.toBeInTheDocument()

    const { container: uncoveredContainer } = render(<CountryFlag countryName="Kiribati" />)
    expect(failedContainer.textContent).toBe(uncoveredContainer.textContent)
    expect(failedContainer.innerHTML).toBe(uncoveredContainer.innerHTML)
  })

  it('resets the failure when a new flagUrl is supplied for a different country', () => {
    render(<CountryFlag flagUrl="/game-assets/flags/does-not-exist.svg" countryName="Kiribati" />)
    fireEvent.error(document.querySelector('img') as HTMLImageElement)
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('renders nothing at all when countryName is blank', () => {
    const { container } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing at all when countryName is null or undefined', () => {
    const { container: nullContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName={null} />,
    )
    expect(nullContainer).toBeEmptyDOMElement()

    const { container: undefinedContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName={undefined} />,
    )
    expect(undefinedContainer).toBeEmptyDOMElement()
  })

  it('renders nothing at all for a whitespace-only countryName', () => {
    const { container } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="   " />)
    expect(container).toBeEmptyDOMElement()
  })

  it('sizes the flag from the icon-sm/icon-md tokens, never a Tailwind size utility', () => {
    const { container: smContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName="France" size="sm" />,
    )
    const smImg = smContainer.querySelector('img') as HTMLImageElement
    expect(smImg.style.height).toBe('var(--ds-icon-sm)')
    expect(smImg.className).not.toMatch(/\bw-\d/)

    const { container: mdContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName="France" size="md" />,
    )
    const mdImg = mdContainer.querySelector('img') as HTMLImageElement
    expect(mdImg.style.height).toBe('var(--ds-icon-md)')
  })

  it('sets the box width to a 4:3 ratio of the height token, never a square', () => {
    const { container } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = container.querySelector('img') as HTMLImageElement
    expect(img.style.width).toBe('calc(var(--ds-icon-sm) * 4 / 3)')
  })

  it('is never a tab stop — the flag carries no tabindex and no title', () => {
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = document.querySelector('img')
    expect(img).not.toHaveAttribute('tabindex')
    expect(img).not.toHaveAttribute('title')
  })

  it('uses object-fit contain, never stretched or cropped', () => {
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = document.querySelector('img') as HTMLImageElement
    expect(img.style.objectFit).toBe('contain')
  })
})
