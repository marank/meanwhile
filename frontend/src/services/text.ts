/**
 * The text, or `undefined` when it is missing or empty, for a fallback with `??`:
 * `nonEmpty(user.display_name) ?? user.email`. Names and URLs the server leaves empty mean "none".
 */
export function nonEmpty(value: string | null | undefined): string | undefined {
  // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- an empty string counts as missing here
  return value || undefined
}
