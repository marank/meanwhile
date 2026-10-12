/**
 * The values of a settings form that differ from the saved ones. Forms save only these, so a
 * week layout nobody set keeps following the app's defaults, also when an admin changes them later.
 */
export function changedValues<T extends object>(values: Partial<T>, saved: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(values).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(saved[key as keyof T])),
  ) as Partial<T>
}
