import { describe, expect, it } from 'vitest'

import type { AgentPlan, AgentPlanExtra, AgentPlanItem } from '../../api/generated/types.gen'
import { missingPrices } from './quoteReadiness'

const ITEM: AgentPlanItem = {
  id: 'i1',
  offer_id: 'o1',
  day: 2,
  quantity: 1,
  note: null,
  kind: 'guide',
  title: 'Chania à pied',
  description: null,
  available: true,
  negotiated_price: null,
  removed: false,
  partner_name: 'Kriti Walks',
  partner_contact_email: 'hello@kriti-walks.example',
  partner_contact_phone: '+30 210 000 0000',
}

const ON_QUOTE: AgentPlanExtra = {
  extra_id: 'e1',
  label: 'Airport transfer',
  pricing: 'on_quote',
  unit: 'trip',
  price_eur: null,
  needs_quantity_check: false,
  confirmed: false,
}

const INCLUDED: AgentPlanExtra = { ...ON_QUOTE, extra_id: 'e2', label: 'Welcome drink', pricing: 'included' }

const PER_NIGHT: AgentPlanExtra = {
  ...ON_QUOTE,
  extra_id: 'e3',
  label: 'Late check-out',
  pricing: 'supplement',
  unit: 'night',
  price_eur: '20.00',
  needs_quantity_check: true,
  confirmed: false,
}

const PLAN: AgentPlan = {
  id: 'p1',
  wish_id: 'w1',
  status: 'negotiating',
  summary: 'Une semaine calme entre mer et vieille ville.',
  items: [],
  extras: [],
  total: '0.00',
  ready_to_quote: true,
  budget_max: null,
  currency: 'EUR',
  over_budget: false,
  assigned_agent_id: 'a1',
  wish_text: 'Une semaine calme.',
  country: 'Greece',
  city: 'Chania',
  persons: 2,
  start_date: '2027-05-12',
  end_date: '2027-05-19',
}

describe('missingPrices', () => {
  it('lists a kept item without a negotiated price', () => {
    const plan = { ...PLAN, items: [ITEM] }

    expect(missingPrices(plan)).toEqual([{ kind: 'item', id: 'i1', day: 2, title: 'Chania à pied' }])
  })

  it('ignores a removed item without a price', () => {
    const plan = { ...PLAN, items: [{ ...ITEM, removed: true }] }

    expect(missingPrices(plan)).toEqual([])
  })

  it('lists an on_quote extra without a price, but not an included one', () => {
    const plan = { ...PLAN, extras: [ON_QUOTE, INCLUDED] }

    expect(missingPrices(plan)).toEqual([{ kind: 'extra', id: 'e1', label: 'Airport transfer' }])
  })

  it('lists a supplement that needs a quantity check until the agent confirms it', () => {
    const unconfirmed = { ...PLAN, extras: [PER_NIGHT] }
    const confirmed = { ...PLAN, extras: [{ ...PER_NIGHT, confirmed: true }] }

    expect(missingPrices(unconfirmed)).toEqual([{ kind: 'extra', id: 'e3', label: 'Late check-out' }])
    expect(missingPrices(confirmed)).toEqual([])
  })

  it('lists nothing when every kept line has its price', () => {
    const plan = {
      ...PLAN,
      items: [{ ...ITEM, negotiated_price: '450.00' }],
      extras: [{ ...ON_QUOTE, price_eur: '60.00' }, INCLUDED, { ...PER_NIGHT, confirmed: true }],
    }

    expect(missingPrices(plan)).toEqual([])
  })

  it('lists nothing for a plan without items or extras', () => {
    expect(missingPrices(PLAN)).toEqual([])
  })
})
