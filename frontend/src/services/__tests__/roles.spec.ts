import { describe, expect, it } from 'vitest'
import { hasRole } from '../roles'

describe('hasRole', () => {
  it('allows a role and the ones below it', () => {
    expect(hasRole('manage', 'full')).toBe(true)
    expect(hasRole('manage', 'manage')).toBe(true)
    expect(hasRole('manage', 'owner')).toBe(false)
    expect(hasRole('read', 'own')).toBe(false)
  })

  it('allows nothing without a role', () => {
    expect(hasRole(null, 'read')).toBe(false)
    expect(hasRole(undefined, 'read')).toBe(false)
  })
})
