import { describe, expect, it } from 'vitest'

import { initials } from './initials'

describe('initials', () => {
  it('takes the first letter of the first two words', () => {
    expect(initials('Camille Martin')).toBe('CM')
    expect(initials('jean pierre dupont')).toBe('JP')
  })

  it('works on an email when there is no name', () => {
    expect(initials('lea@example.com')).toBe('LE')
  })
  it('keeps a character made of two UTF-16 units whole', () => {
    expect(initials('😀 Martin')).toBe('😀M')
    expect(initials('𝒜da Lovelace')).toBe('𝒜L')
  })
})
