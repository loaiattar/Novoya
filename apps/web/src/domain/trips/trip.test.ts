import { describe, expect, it } from 'vitest'

import { type TripFacts, tripStatus, tripTarget } from './trip'

const trip = (overrides: Partial<TripFacts> = {}): TripFacts => ({
  wish_id: 'w1',
  status: 'answered',
  plan_id: null,
  plan_status: null,
  quote_id: null,
  ...overrides,
})

describe('tripTarget', () => {
  it('opens the quote once there is one', () => {
    expect(tripTarget(trip({ plan_id: 'p1', plan_status: 'quoted', quote_id: 'q1' }))).toEqual({
      kind: 'quote',
      quoteId: 'q1',
    })
  })

  it('opens the plan when it is proposed or requested', () => {
    expect(tripTarget(trip({ plan_id: 'p1', plan_status: 'proposed' }))).toEqual({ kind: 'plan', planId: 'p1' })
    expect(tripTarget(trip({ plan_id: 'p1', plan_status: 'requested' }))).toEqual({ kind: 'plan', planId: 'p1' })
  })

  it('opens the panel of a wish not answered yet', () => {
    expect(tripTarget(trip({ status: 'panel_shown' }))).toEqual({ kind: 'panel', wishId: 'w1' })
  })

  it('opens the wish page for a draft or a destination not covered', () => {
    expect(tripTarget(trip({ status: 'draft' }))).toEqual({ kind: 'wish' })
    expect(tripTarget(trip({ status: 'not_covered' }))).toEqual({ kind: 'wish' })
  })
})

describe('tripStatus', () => {
  it('follows the plan when there is one', () => {
    expect(tripStatus({ status: 'planned', plan_status: 'proposed' })).toBe('plan_proposed')
    expect(tripStatus({ status: 'planned', plan_status: 'requested' })).toBe('sent')
    expect(tripStatus({ status: 'planned', plan_status: 'negotiating' })).toBe('in_progress')
    expect(tripStatus({ status: 'planned', plan_status: 'quoted' })).toBe('quoted')
    expect(tripStatus({ status: 'planned', plan_status: 'accepted' })).toBe('accepted')
    expect(tripStatus({ status: 'planned', plan_status: 'rejected' })).toBe('rejected')
  })

  it('follows the wish when there is no plan', () => {
    expect(tripStatus({ status: 'draft', plan_status: null })).toBe('draft')
    expect(tripStatus({ status: 'panel_shown', plan_status: null })).toBe('panel_shown')
    expect(tripStatus({ status: 'answered', plan_status: null })).toBe('answered')
  })
})
