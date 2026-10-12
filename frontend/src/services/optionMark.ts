import type { SearchResult } from '@/api'
import { resourceIcon } from '@/services/resourceIcons'

export type OptionMark = { kind: 'color'; color: string } | { kind: 'icon'; icon: string }

/** What an option of a picker shows before its label: a category's color, or a resource's icon. */
export function optionMark(option: SearchResult): OptionMark | null {
  const meta = option.meta ?? {}
  if (option.type === 'category' && typeof meta.color === 'string') return { kind: 'color', color: meta.color }
  if (option.type === 'resource' && typeof meta.icon === 'string' && resourceIcon(meta.icon)) {
    return { kind: 'icon', icon: meta.icon }
  }
  return null
}
