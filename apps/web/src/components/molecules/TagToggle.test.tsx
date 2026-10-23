import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { TagToggle } from './TagToggle'

describe('TagToggle', () => {
  it('tells screen readers whether the tag is picked', () => {
    const { rerender } = render(<TagToggle label="Calme" selected={false} onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: 'Calme' })).toHaveAttribute('aria-pressed', 'false')

    rerender(<TagToggle label="Calme" selected onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: 'Calme' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('calls onToggle when pressed', () => {
    const onToggle = vi.fn()
    render(<TagToggle label="Calme" selected={false} onToggle={onToggle} />)

    fireEvent.click(screen.getByRole('button', { name: 'Calme' }))

    expect(onToggle).toHaveBeenCalledOnce()
  })
})
