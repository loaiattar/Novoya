import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlanNotes } from './PlanNotes'

describe('PlanNotes', () => {
  it('always says the price will come in a quote', () => {
    render(<PlanNotes basedOnPreferences />)

    expect(screen.getByText(/price will come in a quote/i)).toBeInTheDocument()
  })

  it('says nothing about preferences when the plan follows them', () => {
    render(<PlanNotes basedOnPreferences />)

    expect(screen.queryByText(/not based on your preferences/i)).not.toBeInTheDocument()
  })

  it('warns when the plan is not based on preferences', () => {
    render(<PlanNotes basedOnPreferences={false} />)

    expect(screen.getByText(/not based on your preferences/i)).toBeInTheDocument()
  })
}) 