import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { useThemeStore } from '../theme'

/** A system colour scheme the test can switch, as the browser's media query would report it. */
function systemScheme(dark: boolean) {
  const listeners: ((event: { matches: boolean }) => void)[] = []
  const media = {
    matches: dark,
    addEventListener: (_type: string, listener: (event: { matches: boolean }) => void) => listeners.push(listener),
  }
  vi.stubGlobal('matchMedia', () => media)
  return (next: boolean) => listeners.forEach((listener) => listener({ matches: next }))
}

const root = document.documentElement

describe('theme store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => root.classList.remove('dark'))

  it('follows the system until one picks a theme', async () => {
    const switchSystem = systemScheme(true)
    const theme = useThemeStore()
    theme.init()
    theme.init()
    expect(theme.preference).toBe('system')
    expect(root.classList.contains('dark')).toBe(true)
    expect(root.style.colorScheme).toBe('dark')

    switchSystem(false)
    await nextTick()
    expect(theme.resolved).toBe('light')
    expect(root.classList.contains('dark')).toBe(false)
  })

  it('toggles and remembers the choice', async () => {
    systemScheme(false)
    const theme = useThemeStore()
    theme.init()
    theme.toggle()
    await nextTick()
    expect(theme.isDark).toBe(true)
    expect(localStorage.getItem('theme')).toBe('dark')
    theme.toggle()
    expect(theme.resolved).toBe('light')
  })

  it('starts with the remembered choice, ignoring unknown values', () => {
    systemScheme(false)
    localStorage.setItem('theme', 'dark')
    expect(useThemeStore().preference).toBe('dark')
    setActivePinia(createPinia())
    localStorage.setItem('theme', 'purple')
    expect(useThemeStore().preference).toBe('system')
  })
})
