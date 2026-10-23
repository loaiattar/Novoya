import { afterEach, describe, expect, it } from 'vitest'

import { googleSignInUrl } from './auth'
import { client } from './generated/client.gen'

describe('googleSignInUrl', () => {
  afterEach(() => client.setConfig({ baseUrl: 'http://api.test' }))

  it('goes through the same-origin proxy by default', () => {
    client.setConfig({ baseUrl: '/api' })

    expect(googleSignInUrl('/wishes?id=1')).toBe('/api/auth/google/login?redirect_to=%2Fwishes%3Fid%3D1')
  })

  it('does not double the slash when the base URL ends with one', () => {
    client.setConfig({ baseUrl: 'http://api.test/' })

    expect(googleSignInUrl('/')).toBe('http://api.test/auth/google/login?redirect_to=%2F')
  })
})
