import { describe, expect, it } from 'vitest'

import { localIsoDate } from './dates'

describe('localIsoDate', () => {
  it('writes the local day with two-digit month and day', () => {
    expect(localIsoDate(new Date(2026, 4, 2, 23, 30))).toBe('2026-05-02')
  })
})
