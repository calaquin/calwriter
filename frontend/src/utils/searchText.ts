// Search 2.0 (P1.1) client-side counterpart to services.html_to_search_text
// on the backend. Both MUST walk their respective DOM/HTML with the exact
// same block/inline rules -- a server-found occurrence's startOffset/
// endOffset only resolves to the right place in the live editor if this
// produces byte-identical canonical text for the same content. Block-level
// tags (and <br>) become a "\n" boundary; inline formatting tags and plain
// text stay contiguous, so a word split across inline tags (e.g.
// "<strong>Talak</strong>tei") remains one searchable/highlightable word.
const SEARCH_BLOCK_TAGS = new Set(['P', 'DIV', 'LI', 'UL', 'OL', 'HR'])

/** Canonical searchable plain-text form of `root`'s content, matching
 * services.html_to_search_text exactly. */
export function canonicalSearchText(root: Node): string {
  function walk(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? ''
    if (node.nodeType !== Node.ELEMENT_NODE) return ''
    const el = node as Element
    if (el.tagName === 'BR') return '\n'
    if (el.tagName === 'IMG') return ''
    const text = Array.from(el.childNodes).map(walk).join('')
    return SEARCH_BLOCK_TAGS.has(el.tagName) ? text + '\n' : text
  }
  return Array.from(root.childNodes).map(walk).join('')
}

export interface DomOffset {
  node: Node
  offset: number
}

/** Inverse of canonicalSearchText: resolves a canonical-text character
 * offset back to a concrete DOM (node, offset) position usable in a Range.
 * A "\n" boundary from a block tag or <br> has no DOM text node of its own
 * to point into -- landing exactly on one resolves to the nearest
 * addressable text position instead (clamped, never throws). Returns null
 * only when `root` contains no text at all. */
export function resolveCanonicalOffset(root: Node, targetOffset: number): DomOffset | null {
  let remaining = targetOffset
  let lastText: DomOffset | null = null

  function indexInParent(node: Node): number {
    const parent = node.parentNode
    if (!parent) return 0
    return Array.prototype.indexOf.call(parent.childNodes, node)
  }

  function visit(node: Node): DomOffset | null {
    if (node.nodeType === Node.TEXT_NODE) {
      const length = node.textContent?.length ?? 0
      if (length > 0) lastText = { node, offset: length }
      if (remaining <= length) return { node, offset: Math.max(0, remaining) }
      remaining -= length
      return null
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return null
    const el = node as Element
    if (el.tagName === 'BR') {
      if (remaining <= 1) return { node: el.parentNode ?? el, offset: indexInParent(el) + 1 }
      remaining -= 1
      return null
    }
    if (el.tagName === 'IMG') return null
    for (const child of Array.from(el.childNodes)) {
      const hit = visit(child)
      if (hit) return hit
    }
    if (SEARCH_BLOCK_TAGS.has(el.tagName)) {
      if (remaining <= 1) return { node: el, offset: el.childNodes.length }
      remaining -= 1
    }
    return null
  }

  for (const child of Array.from(root.childNodes)) {
    const hit = visit(child)
    if (hit) return hit
  }
  return lastText
}

/** Escapes every regex-special character so `text` can only ever match
 * itself literally. */
function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Case-insensitive, literal (non-regex) substring match offsets in
 * `haystack`, left to right, non-overlapping -- the client-side
 * counterpart to services.find_literal_occurrences, used to re-locate a
 * search result's occurrence against the *current* live editor content
 * (see ChapterEditor's findRequest) rather than trusting offsets that may
 * be stale by the time the user clicks a result. */
export function findLiteralOccurrences(haystack: string, needle: string): [number, number][] {
  if (!needle) return []
  const pattern = new RegExp(escapeRegExp(needle), 'giu')
  return Array.from(haystack.matchAll(pattern), (m) => [m.index ?? 0, (m.index ?? 0) + m[0].length])
}

/** Builds a Range for [startOffset, endOffset) in `root`'s canonical text,
 * or null if either endpoint can't be resolved (an empty editor, or a
 * pathological/stale offset past the end of the text). */
export function rangeForCanonicalOffsets(root: Node, startOffset: number, endOffset: number): Range | null {
  const start = resolveCanonicalOffset(root, startOffset)
  const end = resolveCanonicalOffset(root, endOffset)
  if (!start || !end) return null
  const range = document.createRange()
  try {
    range.setStart(start.node, start.offset)
    range.setEnd(end.node, end.offset)
  } catch {
    return null
  }
  return range
}
