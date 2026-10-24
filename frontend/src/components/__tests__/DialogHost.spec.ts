import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { i18n } from '@/i18n'
import { alert, choose, confirm, dialog, prompt, submitDialog } from '@/services/dialog'
import DialogHost from '../DialogHost.vue'

let wrapper: VueWrapper

const panel = () => document.querySelector<HTMLElement>('[role="dialog"]')
const buttons = () => [...panel()!.querySelectorAll<HTMLButtonElement>('button')]
const button = (text: string) => buttons().find((b) => b.textContent?.trim() === text)!

beforeEach(() => {
  i18n.global.locale.value = 'en'
  wrapper = mount(DialogHost, { global: { plugins: [i18n] }, attachTo: document.body })
})

afterEach(() => {
  if (dialog.open) submitDialog()
  wrapper.unmount()
})

describe('DialogHost', () => {
  it('shows nothing until a dialog is opened', () => {
    expect(panel()).toBeNull()
  })

  it('shows an alert with a default title and only an OK button', async () => {
    const answer = alert('Saved.')
    await flushPromises()
    expect(panel()!.textContent).toContain('Notice')
    expect(panel()!.textContent).toContain('Saved.')
    expect(buttons().map((b) => b.textContent?.trim())).toEqual(['', 'OK'])
    button('OK').click()
    await expect(answer).resolves.toBeUndefined()
    await flushPromises()
    expect(panel()).toBeNull()
  })

  it('answers a confirmation with yes or no', async () => {
    let answer = confirm('Delete it?', 'Delete')
    await flushPromises()
    expect(panel()!.textContent).toContain('Delete')
    button('Yes').click()
    await expect(answer).resolves.toBe(true)

    answer = confirm('Delete it?')
    await flushPromises()
    expect(panel()!.textContent).toContain('Confirm')
    button('No').click()
    await expect(answer).resolves.toBe(false)
  })

  it('treats closing a confirmation as no', async () => {
    const answer = confirm('Delete it?')
    await flushPromises()
    panel()!.querySelector<HTMLButtonElement>('button[aria-label="Close"]')!.click()
    await expect(answer).resolves.toBe(false)
  })

  it('focuses the prompt and answers with the text entered on Enter', async () => {
    const answer = prompt('Name?', 'Work')
    await flushPromises()
    const input = panel()!.querySelector('input')!
    expect(document.activeElement).toBe(input)
    expect(input.value).toBe('Work')
    input.value = 'Home'
    input.dispatchEvent(new Event('input'))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    await expect(answer).resolves.toBe('Home')
  })

  it('answers a cancelled prompt with nothing', async () => {
    const answer = prompt('Name?')
    await flushPromises()
    button('Cancel').click()
    await expect(answer).resolves.toBeNull()
  })

  it('answers with the choice clicked', async () => {
    const answer = choose('Which?', [
      { value: 'one', label: 'Only this' },
      { value: 'all', label: 'All of them' },
    ])
    await flushPromises()
    expect(buttons().some((b) => b.textContent?.trim() === 'OK')).toBe(false)
    button('All of them').click()
    await expect(answer).resolves.toBe('all')
  })

  it('answers a cancelled choice with nothing', async () => {
    const answer = choose('Which?', [{ value: 'one', label: 'Only this' }])
    await flushPromises()
    button('Cancel').click()
    await expect(answer).resolves.toBeNull()
  })
})
