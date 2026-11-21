// jsdom doesn't lay out pages, so it has no scrolling; components may still ask for it.
// eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- missing in jsdom despite the DOM types
Element.prototype.scrollIntoView ??= function () {}

import { afterEach, vi } from 'vitest'

// A fake backend (or any other stubbed global) lasts for one test only.
afterEach(() => {
  vi.unstubAllGlobals()
})
