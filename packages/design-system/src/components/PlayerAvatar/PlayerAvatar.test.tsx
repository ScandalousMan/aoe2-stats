import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PlayerAvatar } from './index'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SOURCE = readFileSync(resolve(__dirname, 'index.tsx'), 'utf-8')

const HASH = '0123456789abcdef0123456789abcdef01234567'

describe('PlayerAvatar', () => {
  it('builds the Steam CDN URL from the hash, URL-encoded', () => {
    const { container } = render(<PlayerAvatar avatarHash={HASH} />)
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', `https://avatars.steamstatic.com/${HASH}_full.jpg`)
  })

  it('URL-encodes a hash containing characters that would otherwise change the URL shape', () => {
    const unsafeHash = 'abc/def?x=1&y=2 z'
    const { container } = render(<PlayerAvatar avatarHash={unsafeHash} />)
    const img = container.querySelector('img') as HTMLImageElement
    expect(img.getAttribute('src')).toBe(
      `https://avatars.steamstatic.com/${encodeURIComponent(unsafeHash)}_full.jpg`,
    )
  })

  it('never gives the image an accessible name — alt is always empty, decorative', () => {
    render(<PlayerAvatar avatarHash={HASH} />)
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('alt', '')
  })

  it('sets referrerpolicy="no-referrer" — the CDN must not learn which profile was viewed', () => {
    render(<PlayerAvatar avatarHash={HASH} />)
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('referrerpolicy', 'no-referrer')
  })

  it('sets loading="lazy", decoding="async" and explicit width/height', () => {
    render(<PlayerAvatar avatarHash={HASH} size="md" />)
    const img = document.querySelector('img')
    expect(img).toHaveAttribute('loading', 'lazy')
    expect(img).toHaveAttribute('decoding', 'async')
    expect(img).toHaveAttribute('width', '64')
    expect(img).toHaveAttribute('height', '64')
  })

  it('renders no <img> and just the frame for an absent hash', () => {
    const { container } = render(<PlayerAvatar avatarHash={undefined} />)
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('.border-border-strong')).toBeInTheDocument()
    expect(container.querySelector('.bg-surface-sunken')).toBeInTheDocument()
  })

  it('renders no <img> and just the frame for a null hash', () => {
    const { container } = render(<PlayerAvatar avatarHash={null} />)
    expect(container.querySelector('img')).not.toBeInTheDocument()
  })

  it('renders no <img> and just the frame for a blank hash', () => {
    const { container } = render(<PlayerAvatar avatarHash="   " />)
    expect(container.querySelector('img')).not.toBeInTheDocument()
  })

  it('removes the image on a failed decode, rendering byte-identically to the absent-hash frame', () => {
    const { container: failedContainer } = render(<PlayerAvatar avatarHash={HASH} />)
    const img = failedContainer.querySelector('img')
    expect(img).toBeInTheDocument()
    fireEvent.error(img as HTMLImageElement)
    expect(failedContainer.querySelector('img')).not.toBeInTheDocument()

    const { container: absentContainer } = render(<PlayerAvatar avatarHash={undefined} />)
    expect(failedContainer.innerHTML).toBe(absentContainer.innerHTML)
  })

  it('resets the failure when a new avatarHash is supplied for a different profile', () => {
    const { rerender, container } = render(<PlayerAvatar avatarHash={HASH} />)
    fireEvent.error(container.querySelector('img') as HTMLImageElement)
    expect(container.querySelector('img')).not.toBeInTheDocument()

    const otherHash = 'fedcba9876543210fedcba9876543210fedcba9'
    rerender(<PlayerAvatar avatarHash={otherHash} />)
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      `https://avatars.steamstatic.com/${otherHash}_full.jpg`,
    )
  })

  it('renders no text or name of its own', () => {
    const { container } = render(<PlayerAvatar avatarHash={HASH} />)
    expect(container.textContent).toBe('')
  })

  it('sizes from the icon-lg/icon-2xl tokens, never a Tailwind size utility', () => {
    const { container: smContainer } = render(<PlayerAvatar avatarHash={HASH} size="sm" />)
    const smFrame = smContainer.firstElementChild as HTMLElement
    expect(smFrame.style.width).toBe('var(--ds-icon-lg)')
    expect(smFrame.className).not.toMatch(/\bw-\d/)

    const { container: mdContainer } = render(<PlayerAvatar avatarHash={HASH} size="md" />)
    const mdFrame = mdContainer.firstElementChild as HTMLElement
    expect(mdFrame.style.width).toBe('var(--ds-icon-2xl)')
  })

  it('keeps width equal to height in every state — the frame is always square', () => {
    const { container: loaded } = render(<PlayerAvatar avatarHash={HASH} />)
    const loadedFrame = loaded.firstElementChild as HTMLElement
    expect(loadedFrame.style.width).toBe(loadedFrame.style.height)

    const { container: empty } = render(<PlayerAvatar avatarHash={undefined} />)
    const emptyFrame = empty.firstElementChild as HTMLElement
    expect(emptyFrame.style.width).toBe(emptyFrame.style.height)
  })

  it('uses border-md radius, border-strong frame and surface-sunken fill in both loaded and empty states', () => {
    const { container: loaded } = render(<PlayerAvatar avatarHash={HASH} />)
    const loadedFrame = loaded.firstElementChild as HTMLElement
    expect(loadedFrame.className).toContain('rounded-md')
    expect(loadedFrame.className).toContain('border-border-strong')
    expect(loadedFrame.className).toContain('bg-surface-sunken')

    const { container: empty } = render(<PlayerAvatar avatarHash={undefined} />)
    const emptyFrame = empty.firstElementChild as HTMLElement
    expect(emptyFrame.className).toContain('rounded-md')
    expect(emptyFrame.className).toContain('border-border-strong')
    expect(emptyFrame.className).toContain('bg-surface-sunken')
  })

  it('marks the frame aria-hidden — the avatar never announces itself, the heading beside it does', () => {
    const { container } = render(<PlayerAvatar avatarHash={HASH} />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
  })

  it('uses object-fit cover, never stretched to a non-square shape', () => {
    render(<PlayerAvatar avatarHash={HASH} />)
    const img = document.querySelector('img') as HTMLImageElement
    expect(img.style.objectFit).toBe('cover')
  })

  it('is never a tab stop — the image carries no tabindex and no title', () => {
    render(<PlayerAvatar avatarHash={HASH} />)
    const img = document.querySelector('img')
    expect(img).not.toHaveAttribute('tabindex')
    expect(img).not.toHaveAttribute('title')
  })

  it('exposes no src, baseUrl or href prop — the source has exactly one occurrence of the CDN host', () => {
    const occurrences = SOURCE.match(/avatars\.steamstatic\.com/g) ?? []
    expect(occurrences).toHaveLength(1)
    expect(SOURCE).not.toMatch(/\bsrc\??:\s*string/)
    expect(SOURCE).not.toMatch(/\bbaseUrl\??:/)
    expect(SOURCE).not.toMatch(/\bhref\??:/)
  })
})
