import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dismissToast, toast, toasts } from '../toast'

beforeEach(() => {
  vi.useFakeTimers()
  toasts.splice(0)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('toast service', () => {
  it('shows success and error messages with their tone', () => {
    toast.success('Saved')
    toast.error('Failed')
    expect(toasts.map(({ message, tone }) => ({ message, tone }))).toEqual([
      { message: 'Saved', tone: 'success' },
      { message: 'Failed', tone: 'error' },
    ])
  })

  it('hides success and error messages after five seconds', () => {
    toast.success('Saved')
    vi.advanceTimersByTime(4999)
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(toasts).toHaveLength(0)
  })

  it('keeps info messages for fifteen seconds', () => {
    toast.info('Reminder')
    expect(toasts[0]!.tone).toBe('info')
    vi.advanceTimersByTime(14_999)
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(toasts).toHaveLength(0)
  })

  it('dismisses one message and leaves the others', () => {
    toast.success('One')
    toast.success('Two')
    dismissToast(toasts[0]!.id)
    expect(toasts.map((t) => t.message)).toEqual(['Two'])
  })

  it('ignores dismissing a message that is already gone', () => {
    toast.success('One')
    const id = toasts[0]!.id
    dismissToast(id)
    dismissToast(id)
    vi.runAllTimers()
    expect(toasts).toHaveLength(0)
  })
})
