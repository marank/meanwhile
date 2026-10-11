import { describe, expect, it } from 'vitest'
import { folderDropZone } from '../useSidebarSortable'

describe('folderDropZone', () => {
  // A 32 px row from y = 100 to 132: 8 px at each edge sort, the middle 16 px drop into the folder.
  it('sorts before or after at the edges and drops into the folder in the middle', () => {
    expect(folderDropZone(100, 132, 103)).toBe('before')
    expect(folderDropZone(100, 132, 107.9)).toBe('before')
    expect(folderDropZone(100, 132, 108)).toBe('into')
    expect(folderDropZone(100, 132, 116)).toBe('into')
    expect(folderDropZone(100, 132, 124)).toBe('into')
    expect(folderDropZone(100, 132, 124.1)).toBe('after')
    expect(folderDropZone(100, 132, 131)).toBe('after')
  })

  it('knows nothing outside the row', () => {
    expect(folderDropZone(100, 132, 99)).toBeNull()
    expect(folderDropZone(100, 132, 133)).toBeNull()
  })
})
