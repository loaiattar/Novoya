import { describe, expect, it } from 'vitest'

import { namespaces, resources } from '.'

function keys(messages: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'object' && value !== null
      ? keys(value as Record<string, unknown>, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  )
}

describe('message files', () => {
  it('has the same screens in every language', () => {
    expect(Object.keys(resources).sort()).toEqual(['en', 'fr'])
    expect(Object.keys(resources.fr).sort()).toEqual(namespaces)
  })

  it.each(namespaces)('fr/%s.json has exactly the keys of the English file', (namespace) => {
    expect(keys(resources.fr[namespace] ?? {}).sort()).toEqual(keys(resources.en[namespace]).sort())
  })

  it.each(namespaces)('fr/%s.json has no empty text', (namespace) => {
    const empty = keys(resources.fr[namespace] ?? {}).filter((key) => {
      const value = key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], resources.fr[namespace])
      return typeof value !== 'string' || value.trim() === ''
    })
    expect(empty).toEqual([])
  })

  // Novoya is the project and the team; the client sees the agency, via {{agency}}.
  // Only the legal notices name the Novoya team, as the site's developer.
  it.each(['en', 'fr'])('%s texts never name Novoya outside the legal notices', (language) => {
    const named = Object.entries(resources[language])
      .filter(([namespace]) => namespace !== 'legal')
      .flatMap(([namespace, messages]) => keys(messages).map((key) => `${namespace}.${key}`))
      .filter((path) => {
        const [namespace, ...parts] = path.split('.')
        const value = parts.reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], resources[language][namespace])
        return typeof value === 'string' && value.includes('Novoya')
      })
    expect(named).toEqual([])
  })
})
