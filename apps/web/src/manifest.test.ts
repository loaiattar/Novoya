import { describe, expect, it } from 'vitest'

import html from '../index.html?raw'
import manifestText from '../public/site.webmanifest?raw'
import { agencyView } from './domain/agency/agency'

const publicFiles = Object.keys(import.meta.glob('../public/*')).map((path) => path.replace('../public', ''))

describe('site.webmanifest', () => {
  it('is linked from index.html', () => {
    expect(html).toContain('<link rel="manifest" href="/site.webmanifest" />')
  })

  it('names the agency and uses its symbol, in files that exist', () => {
    const manifest = JSON.parse(manifestText)
    expect(manifest.short_name).toBe(agencyView('fr').tradeName)
    expect(manifest.name).toBe(agencyView('fr').displayName)
    for (const icon of manifest.icons) expect(publicFiles).toContain(icon.src)
  })
})
