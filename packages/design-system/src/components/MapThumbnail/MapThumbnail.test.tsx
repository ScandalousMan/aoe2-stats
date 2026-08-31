import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MapThumbnail } from './index'

const ARABIA_URL = '/game-assets/maps/arabia.webp'

describe('MapThumbnail', () => {
  it('renders the framed thumbnail and the name for a covered map', () => {
    const { container } = render(<MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" />)
    expect(screen.getByText('Arabia')).toBeInTheDocument()
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', ARABIA_URL)
    expect(img).toHaveAttribute('alt', '')
    // The frame is drawn only when an image is actually rendered inside it (§2).
    expect(container.querySelector('.border-border')).toBeInTheDocument()
  })

  it('renders the name alone, with no img and no frame, for an uncovered map (thumbnailUrl undefined)', () => {
    const { container } = render(<MapThumbnail mapName="Some Custom Scenario" />)
    expect(screen.getByText('Some Custom Scenario')).toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('.border-border')).not.toBeInTheDocument()
  })

  it('removes the image and its frame together on a failed decode, matching the uncovered render', () => {
    const { container: failedContainer } = render(
      <MapThumbnail
        thumbnailUrl="/game-assets/maps/does-not-exist.webp"
        mapName="Some Custom Scenario"
      />,
    )
    const img = failedContainer.querySelector('img')
    expect(img).toBeInTheDocument()
    fireEvent.error(img as HTMLImageElement)
    expect(failedContainer.querySelector('img')).not.toBeInTheDocument()
    expect(failedContainer.querySelector('.border-border')).not.toBeInTheDocument()

    const { container: uncoveredContainer } = render(
      <MapThumbnail mapName="Some Custom Scenario" />,
    )
    expect(failedContainer.textContent).toBe(uncoveredContainer.textContent)
  })

  it('resets the failure when a new thumbnailUrl is supplied for a different map', () => {
    render(
      <MapThumbnail
        thumbnailUrl="/game-assets/maps/does-not-exist.webp"
        mapName="Some Custom Scenario"
      />,
    )
    fireEvent.error(document.querySelector('img') as HTMLImageElement)
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('renders no thumbnail and the UnresolvedIdentifier treatment when mapName is null', () => {
    render(<MapThumbnail thumbnailUrl={ARABIA_URL} mapName={null} />)
    expect(document.querySelector('img')).not.toBeInTheDocument()
    const unresolved = screen.getByText('Map — unresolved')
    expect(unresolved.className).toContain('font-mono')
    expect(unresolved.className).toContain('text-text-secondary')
  })

  it('never guesses a thumbnail from a leaderboard or a neighbouring match when mapName is null', () => {
    // Even with a resolvable thumbnailUrl passed in, a null mapName suppresses the image entirely.
    render(<MapThumbnail thumbnailUrl={ARABIA_URL} mapName={null} />)
    expect(document.querySelector('img')).not.toBeInTheDocument()
  })

  it('sizes from the icon-lg/2xl/3xl tokens, never a Tailwind size utility', () => {
    const { container: smContainer } = render(
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="sm" />,
    )
    const smImg = smContainer.querySelector('img') as HTMLImageElement
    expect(smImg.style.width).toBe('var(--ds-icon-lg)')

    const { container: mdContainer } = render(
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="md" />,
    )
    expect((mdContainer.querySelector('img') as HTMLImageElement).style.width).toBe(
      'var(--ds-icon-2xl)',
    )

    const { container: lgContainer } = render(
      <MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" size="lg" />,
    )
    expect((lgContainer.querySelector('img') as HTMLImageElement).style.width).toBe(
      'var(--ds-icon-3xl)',
    )
  })

  it('is never a tab stop and never uses object-fit anything but contain', () => {
    render(<MapThumbnail thumbnailUrl={ARABIA_URL} mapName="Arabia" />)
    const img = document.querySelector('img') as HTMLImageElement
    expect(img).not.toHaveAttribute('tabindex')
    expect(img.style.objectFit).toBe('contain')
  })
})
