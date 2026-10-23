import { describe, expect, it } from 'vitest'

import { resolveLocale } from './locale'

describe('resolveLocale', () => {
  it("uses the signed-in user's locale first", () => {
    expect(resolveLocale('fr', ['en-US'])).toBe('fr')
    expect(resolveLocale('en', ['fr-FR'])).toBe('en')
  })

  it('prefers the choice made on this browser over its languages', () => {
    expect(resolveLocale(undefined, ['en-US'], 'fr')).toBe('fr')
    expect(resolveLocale(undefined, ['fr-FR'], 'en')).toBe('en')
  })

  it("keeps the signed-in user's locale over the choice made on this browser", () => {
    expect(resolveLocale('en', ['fr-FR'], 'fr')).toBe('en')
  })

  it("falls back to the browser's first language", () => {
    expect(resolveLocale(undefined, ['fr-CA', 'en'])).toBe('fr')
    expect(resolveLocale(undefined, ['FR'])).toBe('fr')
  })

  it('only looks at the first language, like the API', () => {
    expect(resolveLocale(undefined, ['en-GB', 'fr-FR'])).toBe('en')
  })

  it('is English for any other language, or none', () => {
    expect(resolveLocale(undefined, ['de-DE'])).toBe('en')
    expect(resolveLocale(undefined, [])).toBe('en')
    expect(resolveLocale(undefined, ['fr-FR'], undefined)).toBe('fr')
  })
})
