import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Stepper } from './Stepper'

function Travellers() {
  const [value, setValue] = useState(2)
  return (
    <Stepper
      value={value}
      min={1}
      max={3}
      onChange={setValue}
      decreaseLabel="One traveller fewer"
      increaseLabel="One more traveller"
      valueText={`${value} travellers`}
    />
  )
}

describe('Stepper', () => {
  it('keeps the focus on the button when it reaches the limit', () => {
    render(<Travellers />)
    const fewer = screen.getByRole('button', { name: 'One traveller fewer' })
    fewer.focus()

    fireEvent.click(fewer)

    expect(screen.getByText('1 travellers')).toBeInTheDocument()
    expect(fewer).toHaveAttribute('aria-disabled', 'true')
    expect(fewer).not.toBeDisabled()
    expect(fewer).toHaveFocus()
  })

  it('does not go below the minimum', () => {
    render(<Travellers />)
    const fewer = screen.getByRole('button', { name: 'One traveller fewer' })

    fireEvent.click(fewer)
    fireEvent.click(fewer)

    expect(screen.getByText('1 travellers')).toBeInTheDocument()
  })
})
