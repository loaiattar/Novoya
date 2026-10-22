import { describe, expect, it } from 'vitest'

import { canOpen } from './roles'

describe('canOpen', () => {
  it('lets agents, admins and super admins open the agency area', () => {
    expect(canOpen('agent', 'agent')).toBe(true)
    expect(canOpen('admin', 'agent')).toBe(true)
    expect(canOpen('super_admin', 'agent')).toBe(true)
    expect(canOpen('client', 'agent')).toBe(false)
  })

  it('keeps the admin area for admins and super admins', () => {
    expect(canOpen('admin', 'admin')).toBe(true)
    expect(canOpen('super_admin', 'admin')).toBe(true)
    expect(canOpen('agent', 'admin')).toBe(false)
    expect(canOpen('client', 'admin')).toBe(false)
  })
})
