import { describe, expect, it } from 'vitest'
import { dropZone } from '../useSidebarDrag'

describe('dropZone', () => {
  // A 32 px row from y = 100 to 132: 8 px at each edge sort, the middle 16 px drop into the folder.
  it('sorts before or after at the edges and drops into the folder in the middle', () => {
    expect(dropZone(100, 132, 103)).toBe('before')
    expect(dropZone(100, 132, 107.9)).toBe('before')
    expect(dropZone(100, 132, 108)).toBe('into')
    expect(dropZone(100, 132, 124)).toBe('into')
    expect(dropZone(100, 132, 124.1)).toBe('after')
    expect(dropZone(100, 132, 131)).toBe('after')
  })
})
