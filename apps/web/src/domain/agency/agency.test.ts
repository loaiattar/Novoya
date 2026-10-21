import { describe, expect, it } from 'vitest'

import raw from '../../../brand/agency.json'
import schema from '../../../brand/agency.schema.json'
import { agencyView, shown } from './agency'

describe('shown', () => {
  it('keeps a confirmed value', () => {
    expect(shown({ value: 'ok', status: 'confirmed' })).toBe('ok')
  })

  it('hides a value still to check', () => {
    expect(shown({ value: '02 40 00 00 00', status: 'to_check' })).toBeUndefined()
  })
})

describe('agencyView', () => {
  it('exposes confirmed identity and e-mail', () => {
    const agency = agencyView('fr')
    expect(agency.tradeName).toBe('DÉTOUR')
    expect(agency.displayName).toBe('DÉTOUR Voyages')
    expect(agency.foundedYear).toBe(2012)
    expect(agency.email).toBe('contact@detour-voyages.fr')
    expect(agency.logo.src).toBe('/images/logo')
    expect(agency.tagline).toBe('Voyages insolites et week-ends sur mesure')
  })

  it('hides phone, address, Atout France and social links until they are confirmed', () => {
    const agency = agencyView('fr')
    expect(agency.phone).toBeUndefined()
    expect(agency.address).toBeUndefined()
    expect(agency.social).toEqual([])
    expect(agency.legalLines.map((line) => line.key)).toEqual(['publisher', 'email'])
    expect(agency.legalLines.some((line) => line.value.includes('IM044'))).toBe(false)
    expect(agency.legalLines.some((line) => line.value.includes('Écluses'))).toBe(false)
  })

  it('hides English drafts of agency copy', () => {
    const agency = agencyView('en')
    expect(agency.tagline).toBeUndefined()
    expect(agency.descriptionShort).toBeUndefined()
  })
})

// agency.ts reads the JSON with a type cast, so TypeScript does not see it change. These
// checks follow agency.schema.json for what the reader depends on.
describe('agency.json', () => {
  type Entry = { value?: unknown; status?: unknown; translation_status?: Record<string, unknown> }

  function entries(node: unknown, path = ''): [string, Entry][] {
    if (!node || typeof node !== 'object') return []
    const own: [string, Entry][] = 'status' in node ? [[path, node as Entry]] : []
    return own.concat(Object.entries(node).flatMap(([key, child]) => entries(child, `${path}.${key}`)))
  }

  it('has the sections the schema requires', () => {
    for (const section of schema.required) expect(raw).toHaveProperty(section)
  })

  it('marks every value confirmed or to_check, with a value', () => {
    const statuses: unknown[] = schema.$defs.status.enum
    for (const [path, entry] of entries(raw)) {
      expect(statuses, path).toContain(entry.status)
      expect(entry, path).toHaveProperty('value')
      for (const status of Object.values(entry.translation_status ?? {})) expect(statuses, path).toContain(status)
    }
  })
})
