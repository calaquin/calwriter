// Stable reference for "no data yet" fallbacks, so callers doing
// `data ?? EMPTY_ARRAY` don't create a new array every render.
export const EMPTY_ARRAY: readonly never[] = []
