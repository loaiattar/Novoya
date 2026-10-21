import { afterEach, describe, expect, it, vi } from 'vitest'

import { readStoredLocale, storeLocale } from './storedLocale'

describe('the language chosen on this browser', () => {
  afterEach(() => vi.restoreAllMocks())

  it('is remembered', () => {
    storeLocale('fr')
    expect(readStoredLocale()).toBe('fr')
    storeLocale('en')
    expect(readStoredLocale()).toBe('en')
  })

  it('is ignored when the stored value is not a language of the app', () => {
    localStorage.setItem('novoya.locale', 'de')
    expect(readStoredLocale()).toBeUndefined()
  })

  it('is simply not remembered when the storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    expect(() => storeLocale('fr')).not.toThrow()
    expect(readStoredLocale()).toBeUndefined()
  })
})
