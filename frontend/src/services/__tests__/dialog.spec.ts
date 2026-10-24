import { afterEach, describe, expect, it } from 'vitest'
import { alert, choose, confirm, dialog, inputValue, prompt, submitDialog } from '../dialog'

afterEach(() => {
  if (dialog.open) submitDialog()
})

describe('dialog service', () => {
  it('opens an alert with its message and title and resolves once it is closed', async () => {
    const answer = alert('Saved', 'Done')
    expect(dialog).toMatchObject({ open: true, kind: 'alert', message: 'Saved', title: 'Done', choices: [] })
    submitDialog()
    await expect(answer).resolves.toBeUndefined()
    expect(dialog.open).toBe(false)
  })

  it('resolves a confirmation with the answer given', async () => {
    const answer = confirm('Delete it?')
    expect(dialog).toMatchObject({ open: true, kind: 'confirm', message: 'Delete it?', title: '' })
    submitDialog(true)
    await expect(answer).resolves.toBe(true)
  })

  it('prefills a prompt with the default value and resolves with the text entered', async () => {
    const answer = prompt('Name?', 'Work', 'Rename')
    expect(dialog).toMatchObject({ kind: 'prompt', title: 'Rename' })
    expect(inputValue.value).toBe('Work')
    submitDialog('Home')
    await expect(answer).resolves.toBe('Home')
  })

  it('offers choices and resolves with the one picked', async () => {
    const choices = [
      { value: 'a', label: 'A' },
      { value: 'b', label: 'B' },
    ]
    const answer = choose('Which?', choices, 'Pick')
    expect(dialog).toMatchObject({ kind: 'choice', message: 'Which?', title: 'Pick', choices })
    expect(inputValue.value).toBe('')
    submitDialog('b')
    await expect(answer).resolves.toBe('b')
  })

  it('ignores a second answer once the dialog is closed', async () => {
    const answer = confirm('Sure?')
    submitDialog(false)
    submitDialog(true)
    await expect(answer).resolves.toBe(false)
  })
})
