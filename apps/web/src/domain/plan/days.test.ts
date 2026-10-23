import { describe, expect, it } from 'vitest'

import { groupByDay } from './days'

describe('groupByDay', () => {
  it('puts the items under their day, the days in order', () => {
    const items = [
      { id: 'a', day: 2 },
      { id: 'b', day: 1 },
      { id: 'c', day: 2 },
    ]

    expect(groupByDay(items)).toEqual([
      { day: 1, items: [{ id: 'b', day: 1 }] },
      { day: 2, items: [{ id: 'a', day: 2 }, { id: 'c', day: 2 }] },
    ])
  })

  it('gives no day for a plan without items', () => {
    expect(groupByDay([])).toEqual([])
  })
})
