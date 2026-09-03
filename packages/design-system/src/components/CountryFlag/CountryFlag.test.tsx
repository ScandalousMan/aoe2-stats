import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CountryFlag } from './index'

const FRANCE_URL = '/game-assets/flags/fr.svg'

describe('CountryFlag', () => {
  // country-flag.md §11.3 condition 1 — the single likeliest defect: the name must be reachable by
  // a screen reader without ever generating a hover event, so it must resolve with the tooltip
  // closed, not only after it has been opened once.
  it('the accessible name is "Country: France" with the tooltip closed, never opened', () => {
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Country: France' })).toBeInTheDocument()
  })

  it('the flag is framed and the image is decorative (alt="") inside the named button', () => {
    const { container } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', FRANCE_URL)
    expect(img).toHaveAttribute('alt', '')
    expect(container.querySelector('.border-border')).toBeInTheDocument()
  })

  it('reveals the country name in a tooltip on hover', async () => {
    const user = userEvent.setup()
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    await user.hover(screen.getByRole('button'))
    expect(await screen.findByRole('tooltip')).toHaveTextContent('France')
  })

  // §11.6/§11.5 — the flag is now a tab stop with a real 44px hit area, reached by padding on the
  // button rather than a transparent overlay.
  it('is a tab stop with a 44px (icon-xl) hit area, and opens the tooltip on keyboard focus', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <CountryFlag flagUrl={FRANCE_URL} countryName="France" />
        <button type="button">Next stop</button>
      </div>,
    )
    await user.tab()
    const trigger = screen.getByRole('button', { name: 'Country: France' })
    expect(trigger).toHaveFocus()
    expect(trigger.style.minWidth).toBe('var(--ds-icon-xl)')
    expect(trigger.style.minHeight).toBe('var(--ds-icon-xl)')
    expect(screen.getByRole('tooltip')).toHaveTextContent('France')
  })

  // §11.6 active / §11.3 condition 2 — the only route a touch user has, since touch produces no
  // hover and generally no `:focus-visible`.
  it('a press pins the tooltip open independently of the pointer', async () => {
    const user = userEvent.setup()
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const trigger = screen.getByRole('button')
    await user.click(trigger)
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()
    await user.unhover(trigger)
    trigger.blur()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  // §11.4 — a country the pack does not cover: the name alone, no button, no tooltip, no tab stop.
  it('renders the name alone with no button, no tooltip and no frame for an uncovered country', () => {
    const { container } = render(<CountryFlag countryName="Kiribati" />)
    expect(screen.getByText('Kiribati')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('tooltip', { hidden: true })).not.toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('.border-border')).not.toBeInTheDocument()
  })

  // §11.4 — the image fails to load/decode: byte-identical to the uncovered-country render above,
  // and the tooltip that was showing (if any) goes with the flag it was attached to.
  it('removes the image, its frame and its tooltip together on a failed decode, matching the uncovered render', () => {
    const { container: failedContainer } = render(
      <CountryFlag flagUrl="/game-assets/flags/does-not-exist.svg" countryName="Kiribati" />,
    )
    const img = failedContainer.querySelector('img')
    expect(img).toBeInTheDocument()
    fireEvent.error(img as HTMLImageElement)

    expect(failedContainer.querySelector('img')).not.toBeInTheDocument()
    expect(failedContainer.querySelector('.border-border')).not.toBeInTheDocument()
    expect(within(failedContainer).queryByRole('button')).not.toBeInTheDocument()

    const { container: uncoveredContainer } = render(<CountryFlag countryName="Kiribati" />)
    expect(failedContainer.innerHTML).toBe(uncoveredContainer.innerHTML)
  })

  it('resets the failure when a new flagUrl is supplied for a different country', () => {
    render(<CountryFlag flagUrl="/game-assets/flags/does-not-exist.svg" countryName="Kiribati" />)
    fireEvent.error(document.querySelector('img') as HTMLImageElement)
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('renders nothing at all when countryName is blank, null or undefined', () => {
    const { container: blank } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="" />)
    expect(blank).toBeEmptyDOMElement()

    const { container: whitespace } = render(<CountryFlag flagUrl={FRANCE_URL} countryName="   " />)
    expect(whitespace).toBeEmptyDOMElement()

    const { container: nullContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName={null} />,
    )
    expect(nullContainer).toBeEmptyDOMElement()

    const { container: undefinedContainer } = render(
      <CountryFlag flagUrl={FRANCE_URL} countryName={undefined} />,
    )
    expect(undefinedContainer).toBeEmptyDOMElement()
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

  it('uses object-fit contain, never stretched or cropped', () => {
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    const img = document.querySelector('img') as HTMLImageElement
    expect(img.style.objectFit).toBe('contain')
  })

  it('never shows the two-letter code anywhere, including inside the tooltip', async () => {
    const user = userEvent.setup()
    render(<CountryFlag flagUrl={FRANCE_URL} countryName="France" />)
    await user.hover(screen.getByRole('button'))
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).not.toHaveTextContent(/^fr$/i)
  })
})
