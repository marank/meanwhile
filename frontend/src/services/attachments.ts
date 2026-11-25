const UNITS = ['byte', 'kilobyte', 'megabyte', 'gigabyte'] as const

/** A file's size the way people read it: "820 B", "1.5 MB", in the reader's language. */
export function formatSize(bytes: number, locale: string): string {
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  return new Intl.NumberFormat(locale, {
    style: 'unit',
    unit: UNITS[unit],
    unitDisplay: 'short',
    maximumFractionDigits: unit === 0 || value >= 10 ? 0 : 1,
  }).format(value)
}

/** Whether the server takes the text as a link to attach: a web address with a host. */
export function isWebAddress(text: string): boolean {
  try {
    const url = new URL(text.trim())
    return (url.protocol === 'http:' || url.protocol === 'https:') && url.host !== ''
  } catch {
    return false
  }
}
