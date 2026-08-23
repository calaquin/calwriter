import { diffWordsWithSpace } from 'diff'

/** Renders `html` off-screen (attached, not display:none) and reads back
 * .innerText -- unlike .textContent, this collapses each block element
 * (<p>, <div>, <li>, ...) onto its own line the same way the browser
 * actually renders it, which keeps a word-level diff readable paragraph by
 * paragraph instead of running everything together. innerText requires a
 * real layout box, which is why the element has to be attached (just kept
 * out of the visible viewport) rather than a bare detached node -- and
 * specifically moved off-screen rather than visibility:hidden, since
 * innerText only reflects "rendered" text and a visibility:hidden element
 * is spec'd to contribute none, even though it still has layout. */
function htmlToPlainText(html: string): string {
  const el = document.createElement('div')
  el.style.position = 'absolute'
  el.style.left = '-99999px'
  el.style.top = '0'
  el.style.pointerEvents = 'none'
  el.innerHTML = html
  document.body.appendChild(el)
  try {
    return el.innerText
  } finally {
    document.body.removeChild(el)
  }
}

export interface DiffPart {
  value: string
  added?: boolean
  removed?: boolean
}

/** Word-level diff between two chapter versions' HTML content, done on
 * their plain-text rendering rather than the markup -- this catches every
 * real content change (added/removed/reworded text) without trying to also
 * diff formatting, which would need a much heavier rich-text-aware diff to
 * do usefully. */
export function diffVersionsHtml(fromHtml: string, toHtml: string): DiffPart[] {
  return diffWordsWithSpace(htmlToPlainText(fromHtml), htmlToPlainText(toHtml))
}
