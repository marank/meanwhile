import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api'
import { i18n } from '@/i18n'
import { bookingErrorMessage, errorMessage } from '../errors'

describe('errorMessage', () => {
  it('uses the server explanation in its various shapes', () => {
    expect(errorMessage(new ApiError(400, 'plain text', 'Bad Request'), 'fallback')).toBe('plain text')
    expect(errorMessage(new ApiError(400, { detail: 'nested' }, 'Bad Request'), 'fallback')).toBe('nested')
    expect(errorMessage(new ApiError(409, { detail: { message: 'deep' } }, 'Conflict'), 'fallback')).toBe('deep')
    expect(
      errorMessage(new ApiError(400, { errors: [{ message: 'a' }, { code: 'b' }] }, 'Bad Request'), 'fallback'),
    ).toBe('a, b')
  })

  it('falls back when the server sends no explanation', () => {
    expect(errorMessage(new ApiError(500, '', 'Server Error'), 'fallback')).toBe('fallback')
    expect(errorMessage(new ApiError(500, {}, 'Server Error'), 'fallback')).toBe('fallback')
    expect(errorMessage('not an error', 'fallback')).toBe('fallback')
  })

  it('uses the message of other errors', () => {
    expect(errorMessage(new Error('network down'), 'fallback')).toBe('network down')
  })
})

describe('bookingErrorMessage', () => {
  it('explains booking conflicts', () => {
    expect(bookingErrorMessage(new ApiError(409, { detail: 'taken' }, 'Conflict'))).toBe(
      i18n.global.t('booking.conflict'),
    )
  })
})
