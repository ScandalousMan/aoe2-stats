import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Badge } from './index'

describe('Badge', () => {
  it('renders the label as real text', () => {
    render(<Badge variant="accent">Primary</Badge>)
    expect(screen.getByText('Primary')).toBeInTheDocument()
  })

  it('renders nothing when there is no label', () => {
    const { container } = render(<Badge variant="neutral">{null}</Badge>)
    expect(container).toBeEmptyDOMElement()
  })

  it.each(['success', 'warning', 'danger', 'info'] as const)(
    'renders the %s tone with a neutral fill and a tone-coloured label, never a tone-tinted fill',
    (variant) => {
      render(<Badge variant={variant}>Label</Badge>)
      const badge = screen.getByText('Label')
      expect(badge.className).toContain('bg-surface-raised')
      expect(badge.className).toContain(`text-${variant}`)
    },
  )
})
