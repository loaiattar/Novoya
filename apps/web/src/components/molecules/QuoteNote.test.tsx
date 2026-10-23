import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QuoteNote } from './QuoteNote'

describe('QuoteNote', () => {
  it('says the price will come in a quote', () => {
    render(<QuoteNote />)
    expect(screen.getByText(/price will come in a quote/i)).toBeInTheDocument()
  })
})
