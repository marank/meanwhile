import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api'
import { createAvailabilityCache, loadAvailability } from '../availability'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  getAvailability: vi.fn(),
}))

const day = new Date(2030, 0, 7)
const empty: api.Availability = { users: [], resources: [] }

describe('availability cache', () => {
  beforeEach(() => {
    vi.mocked(api.getAvailability).mockReset().mockResolvedValue(empty)
  })

  it('asks the server once per day, people and resources', async () => {
    const cache = createAvailabilityCache()
    const first = loadAvailability(cache, day, ['a', 'b'], ['r'])
    await first.promise
    // Same people in another order: the same entry, already loaded.
    const again = loadAvailability(cache, day, ['b', 'a'], ['r'])
    expect(again).toBe(first)
    expect(again.value).toEqual(empty)
    expect(api.getAvailability).toHaveBeenCalledOnce()

    loadAvailability(cache, day, ['a', 'b', 'c'], ['r'])
    loadAvailability(cache, new Date(2030, 0, 8), ['a', 'b'], ['r'])
    expect(api.getAvailability).toHaveBeenCalledTimes(3)
  })

  it('asks again after a failure', async () => {
    vi.mocked(api.getAvailability).mockRejectedValueOnce(new Error('offline'))
    const cache = createAvailabilityCache()
    await expect(loadAvailability(cache, day, ['a'], []).promise).rejects.toThrow('offline')
    await loadAvailability(cache, day, ['a'], []).promise
    expect(api.getAvailability).toHaveBeenCalledTimes(2)
  })
})
