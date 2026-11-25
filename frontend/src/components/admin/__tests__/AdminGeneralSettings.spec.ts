import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { buttonNamed, clearToasts, toastTexts } from '@/components/__tests__/settingsFixtures'
import AdminGeneralSettings from '../AdminGeneralSettings.vue'
import ImageUploadField from '../ImageUploadField.vue'

const settings: api.AppSettings = {
  id: 1,
  app_name: 'Meanwhile',
  logo_url: 'data:image/png;base64,AAAA',
  favicon_url: '',
  default_first_weekday: 1,
  default_show_weekends: true,
  default_weekend_days: [0, 6],
  default_show_week_numbers: false,
}

let backend: FakeBackend

/** Picks `file` in a file input, as the browser would. */
function pickFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new Event('change'))
}

describe('image upload field', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
  })

  function render(modelValue: string | null, size?: 'sm' | 'lg') {
    const wrapper = mount(ImageUploadField, {
      props: {
        modelValue,
        size,
        label: 'Logo',
        defaultImage: '/logo.svg',
        defaultLabel: "Meanwhile's own logo is shown until you choose one.",
        removeLabel: 'Remove logo',
        'onUpdate:modelValue': (value: string | null) => wrapper.setProps({ modelValue: value }),
      },
      global: { plugins: [i18n] },
    })
    return wrapper
  }

  it('shows the image, or a note without one', async () => {
    const wrapper = render('data:image/png;base64,AAAA', 'sm')
    const labelId = wrapper.get('input[type="file"]').attributes('aria-labelledby')!
    expect(wrapper.get(`[id="${labelId}"]`).text()).toBe('Logo')
    expect(wrapper.get('img').attributes('src')).toBe('data:image/png;base64,AAAA')
    await buttonNamed(wrapper, 'Remove logo').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
    // Without one, the preview shows what the app uses instead, and says so.
    expect(wrapper.get('img').attributes('src')).toBe('/logo.svg')
    expect(wrapper.find('[data-default]').exists()).toBe(true)
    expect(wrapper.text()).toContain("Meanwhile's own logo is shown until you choose one.")
    expect(wrapper.find('button').exists()).toBe(false)
    // The picker is a button-like label of our own, not the browser's "No file chosen".
    expect(wrapper.get('label').text()).toBe('Choose image')
  })

  it('takes a picked file as a data URL', async () => {
    const wrapper = render(null)
    pickFile(
      wrapper.get('input[type="file"]').element as HTMLInputElement,
      new File(['hi'], 'logo.png', { type: 'image/png' }),
    )
    await vi.waitFor(() => expect(wrapper.emitted('update:modelValue')).toEqual([['data:image/png;base64,aGk=']]))
    expect(wrapper.get('img').attributes('src')).toBe('data:image/png;base64,aGk=')
    expect(wrapper.find('[data-default]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('own logo')
    expect(wrapper.get('label').text()).toBe('Choose another')
  })

  it("takes the server's empty value for no image", () => {
    const wrapper = render('')
    expect(wrapper.get('img').attributes('src')).toBe('/logo.svg')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('ignores an empty pick', async () => {
    const wrapper = render(null)
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('admin general settings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/admin/settings': settings,
      'PATCH /api/admin/settings': (req) => ({ ...settings, ...(req.body as object) }),
    })
  })

  async function render() {
    const wrapper = mount(AdminGeneralSettings, { global: { plugins: [i18n] }, attachTo: document.body })
    await flushPromises()
    return wrapper
  }

  it('saves the app name, images and calendar defaults', async () => {
    const wrapper = await render()
    const name = wrapper.get('input:not([type])')
    expect((name.element as HTMLInputElement).value).toBe('Meanwhile')
    await name.setValue('Team Calendar')
    await buttonNamed(wrapper, 'Remove logo').trigger('click')
    await buttonNamed(wrapper, 'Saturday').trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/admin/settings')[0]!.body).toEqual({
      ...settings,
      id: undefined,
      app_name: 'Team Calendar',
      logo_url: null,
      default_weekend_days: [0],
    })
    expect(toastTexts()).toEqual(['Settings saved.'])
    wrapper.unmount()
  })

  it('reports a failed save', async () => {
    backend.on('PATCH /api/admin/settings', reply(500))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    wrapper.unmount()
  })

  it('cannot save when the settings did not load', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    backend.on('GET /api/admin/settings', reply(500))
    const wrapper = await render()
    expect(wrapper.find('input').exists()).toBe(false)
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    vi.restoreAllMocks()
    wrapper.unmount()
  })
})
