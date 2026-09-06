import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Field } from './index'

describe('Field', () => {
  it('associates a real <label> with the control via htmlFor/id, generated when not supplied', () => {
    render(
      <Field label="Display name">
        <input />
      </Field>,
    )
    const input = screen.getByLabelText('Display name')
    const label = screen.getByText('Display name')
    expect(input.id).toBeTruthy()
    expect(label.getAttribute('for')).toBe(input.id)
  })

  it('uses a caller-supplied id instead of generating one, without changing the association', () => {
    render(
      <Field label="Display name" id="display-name">
        <input />
      </Field>,
    )
    const input = screen.getByLabelText('Display name')
    expect(input.id).toBe('display-name')
    expect(screen.getByText('Display name').getAttribute('for')).toBe('display-name')
  })

  it('overwrites an id, aria-describedby or aria-invalid written by hand on the control', () => {
    render(
      <Field label="Display name" hint="Shown publicly">
        <input id="caller-chosen-id" aria-describedby="caller-chosen-id" aria-invalid={false} />
      </Field>,
    )
    const input = screen.getByLabelText('Display name')
    expect(input.id).not.toBe('caller-chosen-id')
    expect(input.getAttribute('aria-describedby')).not.toBe('caller-chosen-id')
    expect(input).toHaveAccessibleDescription('Shown publicly')
  })

  it('associates an optional hint with the control via aria-describedby', () => {
    render(
      <Field label="Profile id" hint="Digits only.">
        <input />
      </Field>,
    )
    const input = screen.getByLabelText('Profile id')
    expect(input).toHaveAccessibleDescription('Digits only.')
  })

  it('renders no hint element and no aria-describedby when no hint or error is given', () => {
    render(
      <Field label="Display name">
        <input />
      </Field>,
    )
    const input = screen.getByLabelText('Display name')
    expect(input).not.toHaveAttribute('aria-describedby')
  })

  it('renders the error as visible text, associates it via aria-describedby alongside the hint, and marks aria-invalid', () => {
    render(
      <Field label="Profile id" hint="Digits only." error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    const input = screen.getByLabelText('Profile id')
    expect(screen.getByText('Profile id — enter digits only.')).toBeInTheDocument()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Digits only. Profile id — enter digits only.')
  })

  it('carries no aria-invalid and no error text when no error is given', () => {
    render(
      <Field label="Profile id">
        <input />
      </Field>,
    )
    expect(screen.getByLabelText('Profile id')).not.toHaveAttribute('aria-invalid')
  })

  it('does not mark an error present at the initial render for assistive-technology announcement', () => {
    render(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    const error = screen.getByText('Profile id — enter digits only.')
    expect(error).not.toHaveAttribute('role')
  })

  it('announces an error that appears after the initial render', () => {
    const { rerender } = render(
      <Field label="Profile id">
        <input />
      </Field>,
    )
    expect(screen.queryByText('Profile id — enter digits only.')).not.toBeInTheDocument()

    rerender(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    const error = screen.getByRole('alert')
    expect(error).toHaveTextContent('Profile id — enter digits only.')
  })

  it('stops re-announcing an error once it has already appeared and remains unchanged', () => {
    const { rerender } = render(
      <Field label="Profile id">
        <input />
      </Field>,
    )
    rerender(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()

    rerender(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Profile id — enter digits only.')).toBeInTheDocument()
  })

  it('announces the error again if it clears and later reappears', () => {
    const { rerender } = render(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    rerender(
      <Field label="Profile id">
        <input />
      </Field>,
    )
    expect(screen.queryByText('Profile id — enter digits only.')).not.toBeInTheDocument()

    rerender(
      <Field label="Profile id" error="Profile id — enter digits only.">
        <input />
      </Field>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Profile id — enter digits only.')
  })

  it('visually hides the label while keeping it in the accessibility tree', () => {
    render(
      <Field label="Search for a player" labelHidden>
        <input />
      </Field>,
    )
    const label = screen.getByText('Search for a player')
    expect(label.className).toMatch(/sr-only/)
    expect(screen.getByLabelText('Search for a player')).toBeInTheDocument()
  })

  it('forwards disabled to the control and never leaves the two able to disagree', () => {
    render(
      <Field label="Display name" disabled>
        <input />
      </Field>,
    )
    expect(screen.getByLabelText('Display name')).toBeDisabled()
  })

  it('loading disables the control and sets aria-busy once on the field', () => {
    const { container } = render(
      <Field label="Display name" loading>
        <input />
      </Field>,
    )
    expect(screen.getByLabelText('Display name')).toBeDisabled()
    const busyRegions = container.querySelectorAll('[aria-busy="true"]')
    expect(busyRegions).toHaveLength(1)
  })

  it('carries no aria-busy attribute when not loading', () => {
    const { container } = render(
      <Field label="Display name">
        <input />
      </Field>,
    )
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(0)
  })

  it('sets the md control height by default and the lg height when size="lg"', () => {
    const { rerender } = render(
      <Field label="Display name">
        <input />
      </Field>,
    )
    expect(screen.getByLabelText('Display name').className).toMatch(/\bh-10\b/)

    rerender(
      <Field label="Display name" size="lg">
        <input />
      </Field>,
    )
    expect(screen.getByLabelText('Display name').className).toMatch(/\bh-12\b/)
  })

  it('preserves a className already on the control alongside the injected size class', () => {
    render(
      <Field label="Display name">
        <input className="caller-class" />
      </Field>,
    )
    const input = screen.getByLabelText('Display name')
    expect(input.className).toMatch(/caller-class/)
    expect(input.className).toMatch(/\bh-10\b/)
  })
})
