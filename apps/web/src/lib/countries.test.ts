import { describe, expect, it } from 'vitest'

import { localizeCountry } from './countries'

describe('localizeCountry', () => {
  it('names a country in the page language', () => {
    expect(localizeCountry('fr', 'Greece')).toBe('Grèce')
    expect(localizeCountry('fr', 'South Korea')).toBe('Corée du Sud')
    expect(localizeCountry('en', 'Greece')).toBe('Greece')
  })

  it('knows the catalogue names Intl spells differently', () => {
    expect(localizeCountry('fr', 'Ivory Coast')).toBe('Côte d’Ivoire')
    expect(localizeCountry('fr', 'Bosnia and Herzegovina')).toBe('Bosnie-Herzégovine')
  })

  it('ignores case and spaces around the name', () => {
    expect(localizeCountry('fr', ' greece ')).toBe('Grèce')
  })

  it('shows an unknown name as given', () => {
    expect(localizeCountry('fr', 'Atlantis')).toBe('Atlantis')
    expect(localizeCountry('fr', 'Unknown Region')).toBe('Unknown Region')
  })
})
