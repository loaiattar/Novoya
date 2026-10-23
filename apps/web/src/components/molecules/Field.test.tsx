import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Input } from '../atoms/Input'
import { Field } from './Field'

function renderField(props: { hint?: string; error?: string }) {
  render(
    <Field label="Budget maximum" {...props}>
      {({ id, describedBy, invalid }) => (
        <Input id={id} aria-describedby={describedBy} aria-invalid={invalid || undefined} />
      )}
    </Field>,
  )
  return screen.getByLabelText('Budget maximum')
}

describe('Field', () => {
  it('links the label to the control', () => {
    expect(renderField({})).toBeInstanceOf(HTMLInputElement)
  })

  it('describes the control with its hint', () => {
    const input = renderField({ hint: 'Partagé uniquement avec votre agent' })

    expect(input).toHaveAccessibleDescription('Partagé uniquement avec votre agent')
    expect(input).not.toHaveAttribute('aria-invalid')
  })

  it('describes the control with the hint and the error, and marks it invalid', () => {
    const input = renderField({ hint: 'En euros', error: 'Indiquez un montant.' })

    expect(input).toHaveAccessibleDescription('En euros Indiquez un montant.')
    expect(input).toHaveAttribute('aria-invalid', 'true')
  })

  it('has no description without hint or error', () => {
    expect(renderField({})).not.toHaveAttribute('aria-describedby')
  })
})
