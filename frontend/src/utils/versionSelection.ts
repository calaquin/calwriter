/** Which side of a version comparison a pane is showing: a specific
 * checkpoint, the live unsaved-to-history "Current" state, or nothing
 * selected at all. Shared between ChapterHistoryModal (compact, modal) and
 * ChapterDiffPage (full page) so both pick versions the same way. */
export type Selection = { kind: 'version'; id: string } | { kind: 'current' } | null

export function sameSelection(a: Selection, b: Selection): boolean {
  if (a === null || b === null) return a === b
  return a.kind === 'current' && b.kind === 'current' ? true : a.kind === 'version' && b.kind === 'version' && a.id === b.id
}

/** Encodes a Selection as a single string for use as a <select> value or a
 * URL query param, since 'current' has no id of its own to key on. */
export function selectionKey(sel: Selection): string {
  if (sel === null) return 'none'
  return sel.kind === 'current' ? 'current' : sel.id
}

export function parseSelectionKey(key: string | null): Selection {
  if (!key || key === 'none') return null
  if (key === 'current') return { kind: 'current' }
  return { kind: 'version', id: key }
}

export function formatVersionTimestamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
