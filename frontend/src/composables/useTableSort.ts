import { computed, ref, type Ref } from 'vue'
import { i18n } from '@/i18n'

export type SortDirection = 'ascending' | 'descending'

/** What a row is sorted by in one column: text (compared like people read it), a number or a flag. */
export type SortValue = string | number | boolean

/**
 * Sorts a table's rows by the column whose header was clicked; clicking it again turns the order
 * round. `columns` names each sortable column and how to read its value from a row; `initial` the
 * column sorted by at first, or null to keep the rows' own order until a header is clicked.
 */
export function useTableSort<Row, Key extends string>(
  rows: Ref<Row[]>,
  columns: Record<Key, (row: Row) => SortValue>,
  initial: NoInfer<Key> | null = null,
) {
  const sortKey = ref(initial) as Ref<Key | null>
  const direction = ref<SortDirection>('ascending')

  const sorted = computed(() => {
    if (sortKey.value === null) return rows.value
    const value = columns[sortKey.value]
    // Numbers in names sort by their value ("Room 2" before "Room 10"), case and accents aside.
    const collator = new Intl.Collator(i18n.global.locale.value, { numeric: true, sensitivity: 'base' })
    const compare = (a: SortValue, b: SortValue) =>
      typeof a === 'string' && typeof b === 'string' ? collator.compare(a, b) : Number(a) - Number(b)
    const sign = direction.value === 'ascending' ? 1 : -1
    return [...rows.value].sort((a, b) => sign * compare(value(a), value(b)))
  })

  function sortBy(key: Key) {
    if (sortKey.value === key) {
      direction.value = direction.value === 'ascending' ? 'descending' : 'ascending'
    } else {
      sortKey.value = key
      direction.value = 'ascending'
    }
  }

  /** For a column's header: its aria-sort, the order it is sorted in or "none". */
  function sortOf(key: Key): SortDirection | 'none' {
    return sortKey.value === key ? direction.value : 'none'
  }

  return { sorted, sortBy, sortOf }
}
