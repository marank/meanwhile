// jsdom doesn't lay out pages, so it has no scrolling; components may still ask for it.
Element.prototype.scrollIntoView ??= function () {}

import { afterEach, vi } from 'vitest'

// A fake backend (or any other stubbed global) lasts for one test only.
afterEach(() => {
  vi.unstubAllGlobals()
})
