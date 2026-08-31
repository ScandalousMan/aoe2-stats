import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PlayerColourSwatch } from './index'

const __dirname = dirname(fileURLToPath(import.meta.url))

const COLOUR_NAMES: Record<number, string> = {
  1: 'Blue',
  2: 'Red',
  3: 'Green',
  4: 'Yellow',
  5: 'Teal',
  6: 'Purple',
  7: 'Grey',
  8: 'Orange',
}

describe('PlayerColourSwatch', () => {
  it.each(Object.entries(COLOUR_NAMES).map(([id, name]) => [Number(id), name] as const))(
    'renders the player-%s fill and "Colour: %s" hidden text',
    (colorId, name) => {
      const { container } = render(
        <PlayerColourSwatch colorId={colorId} playerName="Some player" />,
      )
      const chip = container.querySelector('[aria-hidden="true"]') as HTMLElement
      expect(chip.className).toContain(`bg-player-${colorId}`)
      expect(container).toHaveTextContent(`Colour: ${name}`)
    },
  )

  it('renders a neutral surface-sunken chip and "Colour: not recorded" when colorId is null', () => {
    const { container } = render(<PlayerColourSwatch colorId={null} playerName="Some player" />)
    const chip = container.querySelector('[aria-hidden="true"]') as HTMLElement
    expect(chip.className).toContain('bg-surface-sunken')
    expect(container).toHaveTextContent('Colour: not recorded')
  })

  it('renders the identical neutral chip for an out-of-range colorId — never an error tone', () => {
    const { container: nullContainer } = render(
      <PlayerColourSwatch colorId={null} playerName="Some player" />,
    )
    const { container: outOfRangeContainer } = render(
      <PlayerColourSwatch colorId={99} playerName="Some player" />,
    )
    expect(outOfRangeContainer.innerHTML).toBe(nullContainer.innerHTML)
    expect(outOfRangeContainer.querySelector('.bg-danger')).not.toBeInTheDocument()
  })

  it('renders nothing at all when playerName is blank', () => {
    const { container } = render(<PlayerColourSwatch colorId={1} playerName="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing at all when playerName is null or undefined', () => {
    const { container: nullContainer } = render(
      <PlayerColourSwatch colorId={1} playerName={null} />,
    )
    expect(nullContainer).toBeEmptyDOMElement()

    const { container: undefinedContainer } = render(
      <PlayerColourSwatch colorId={1} playerName={undefined} />,
    )
    expect(undefinedContainer).toBeEmptyDOMElement()
  })

  it('never renders the player name itself — that is the caller’s job', () => {
    const { container } = render(<PlayerColourSwatch colorId={1} playerName="GL.TheViper" />)
    expect(container).not.toHaveTextContent('GL.TheViper')
  })

  it('sizes the chip from the icon-xs/icon-sm tokens, never a Tailwind size utility', () => {
    const { container: xsContainer } = render(
      <PlayerColourSwatch colorId={1} playerName="P" size="xs" />,
    )
    const xsChip = xsContainer.querySelector('[aria-hidden="true"]') as HTMLElement
    expect(xsChip.style.width).toBe('var(--ds-icon-xs)')

    const { container: smContainer } = render(
      <PlayerColourSwatch colorId={1} playerName="P" size="sm" />,
    )
    const smChip = smContainer.querySelector('[aria-hidden="true"]') as HTMLElement
    expect(smChip.style.width).toBe('var(--ds-icon-sm)')
  })

  it('frames every chip in border-strong, in both themes alike (the same token name)', () => {
    const { container } = render(<PlayerColourSwatch colorId={1} playerName="P" />)
    const chip = container.querySelector('[aria-hidden="true"]') as HTMLElement
    expect(chip.className).toContain('border-border-strong')
  })

  it('contains no hex string anywhere in its source', () => {
    const source = readFileSync(resolve(__dirname, 'index.tsx'), 'utf-8')
    expect(source).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })
})
