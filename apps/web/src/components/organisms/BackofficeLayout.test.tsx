import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BackofficeLayout } from './BackofficeLayout'

describe('BackofficeLayout', () => {
  it('keeps the sections without pages off phones, the current one marked', () => {
    render(
      <BackofficeLayout area="Agency" items={[{ label: 'Queue', active: true }, { label: 'Files' }]}>
        <h1>Content</h1>
      </BackofficeLayout>,
    )

    const aside = screen.getByRole('complementary', { name: 'Agency' })
    expect(aside).toHaveClass('hidden', 'md:flex')
    expect(screen.getByText('Queue')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Files')).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('heading', { name: 'Content' })).toBeInTheDocument()
  })
})
