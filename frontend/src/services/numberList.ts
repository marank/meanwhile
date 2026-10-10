// Comma-separated lists of numbers as typed into text fields, e.g. days of the month "1, 15, +".
// "+" stands for the last one (stored as -1, as in RFC 5545).

export const LAST = -1

/** Ascending and without duplicates; the last one (-1) goes at the end. */
export function sortWithLastAtEnd(numbers: number[]): number[] {
  return [...new Set(numbers)].sort((a, b) => (a === LAST ? Infinity : a) - (b === LAST ? Infinity : b))
}

/** The numbers in `text`, or null if it is empty or anything in it is out of range. */
export function parseNumberList(text: string, min: number, max: number, allowLast: boolean): number[] | null {
  const tokens = text.split(/[\s,;]+/).filter(Boolean)
  if (!tokens.length) return null
  const numbers: number[] = []
  for (const token of tokens) {
    if (allowLast && token === '+') {
      numbers.push(LAST)
      continue
    }
    if (!/^\d+$/.test(token)) return null
    const number = Number(token)
    if (number < min || number > max) return null
    numbers.push(number)
  }
  return sortWithLastAtEnd(numbers)
}

export function formatNumberList(numbers: number[]): string {
  return sortWithLastAtEnd(numbers)
    .map((number) => (number === LAST ? '+' : String(number)))
    .join(', ')
}
