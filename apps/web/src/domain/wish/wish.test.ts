import { describe, expect, it } from 'vitest'

import { destinationLabel, destinationPhoto, destinationPlace, FALLBACK_PHOTO } from './destination'
import { sendWishError, sendWishErrorKey, WISH_MAX_LENGTH, wishTextError } from './wish'

describe('wishTextError', () => {
  it('accepts a sentence', () => {
    expect(wishTextError('Une semaine calme au bord de la mer')).toBeNull()
  })

  it('refuses an empty or blank wish', () => {
    expect(wishTextError('')).toBe('wish.empty')
    expect(wishTextError('   \n ')).toBe('wish.empty')
  })

  it('refuses more than the API takes, ignoring the spaces around', () => {
    expect(wishTextError(` ${'a'.repeat(WISH_MAX_LENGTH)} `)).toBeNull()
    expect(wishTextError('a'.repeat(WISH_MAX_LENGTH + 1))).toBe('wish.tooLong')
  })
})

describe('sendWishErrorKey', () => {
  it('explains a refused wish and rate limiting, with a fallback', () => {
    expect(sendWishErrorKey('invalid_wish')).toBe('wish.invalid')
    expect(sendWishErrorKey('too_many_requests')).toBe('wish.tooManyRequests')
    expect(sendWishErrorKey(undefined)).toBe('wish.unknown')
  })
})

describe('sendWishError', () => {
  it('keeps the usual message without Retry-After, and names the wait when it is there', () => {
    expect(sendWishError('too_many_requests')).toEqual({ key: 'wish.tooManyRequests' })
    expect(sendWishError('too_many_requests', 720)).toEqual({ key: 'rateLimit.waitMinutes', count: 12 })
    expect(sendWishError('invalid_wish', 720)).toEqual({ key: 'wish.invalid' })
  })
})

describe('destinationPhoto', () => {
  it('uses the city first, then the country, ignoring case', () => {
    expect(destinationPhoto({ city: 'Chania', country: 'Greece' })).toBe('/images/elounda-sea-view')
    expect(destinationPhoto({ city: 'Athens', country: 'greece' })).toBe('/images/crete-coast')
    expect(destinationPhoto({ city: null, country: 'Morocco' })).toBe('/images/marrakech-riad')
  })

  it('falls back to a neutral photo', () => {
    expect(destinationPhoto({ city: 'Kyoto', country: 'Japan' })).toBe(FALLBACK_PHOTO)
  })
})

describe('destinationLabel and destinationPlace', () => {
  it('name the city when there is one', () => {
    expect(destinationLabel({ city: 'Biarritz', country: 'France' })).toBe('Biarritz · France')
    expect(destinationLabel({ city: null, country: 'France' })).toBe('France')
    expect(destinationPlace({ city: 'Biarritz', country: 'France' })).toBe('Biarritz')
    expect(destinationPlace({ city: null, country: 'Morocco' })).toBe('Morocco')
  })
})
