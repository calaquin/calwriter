import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { useShortcutsModal } from '../context/ShortcutsModalContext'
import { copyText } from '../utils/clipboard'
import { canonicalSearchText, findLiteralOccurrences, rangeForCanonicalOffsets } from '../utils/searchText'
import { api } from '../api/client'
import type {
  InternalReferenceResolution,
  InternalReferenceTarget,
  InternalReferenceTargetType,
} from '../api/types'
import LinkDialog from './LinkDialog'

const FULL_WIDTH_KEY = 'calwriter:editorFullWidth'

// Continuous typing/deleting coalesces into one history entry per pause of
// this length, roughly matching how native browser undo groups keystrokes
// into "bursts" instead of one entry per character -- see the history
// helpers declared inside ChapterEditor for why native undo/redo isn't used
// at all any more (list/checklist operations are plain DOM mutations that
// never participated in it reliably, and a coherent editor can't have one
// history for typing and a separate one for everything else).
const TYPING_HISTORY_COALESCE_MS = 500
// Bounds memory for a very long editing session; oldest entries drop off
// the front once exceeded (see commitHistorySnapshot).
const HISTORY_LIMIT = 100

// Search 2.0 (P1.1): the CSS Custom Highlight API registry name this
// editor's jump-to-occurrence highlight is registered under (see
// applySearchHighlight/clearSearchHighlight). CSS.highlights is a single
// *global* registry shared by the whole page, not scoped per component --
// using one fixed, namespaced key means a later call always cleanly
// replaces (not accumulates alongside) whatever this editor highlighted
// before, and unmount/chapter-switch cleanup has one specific key to drop.
const SEARCH_HIGHLIGHT_NAME = 'calwriter-search-match'
// Custom Highlight API support -- Safari/Chrome/Edge have it; where it's
// unavailable (older Firefox), the Selection API is used instead (see
// applySearchHighlight), which is non-DOM-mutating but self-clears on the
// browser's own native click/type behavior rather than needing explicit
// teardown the way a Highlight registry entry does.
const supportsCustomHighlight =
  typeof CSS !== 'undefined' && 'highlights' in CSS && typeof Highlight !== 'undefined'

function clearSearchHighlight() {
  if (supportsCustomHighlight) CSS.highlights.delete(SEARCH_HIGHLIGHT_NAME)
}

function applySearchHighlight(range: Range) {
  if (supportsCustomHighlight) {
    CSS.highlights.set(SEARCH_HIGHLIGHT_NAME, new Highlight(range))
    return
  }
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
}

// Centers the match vertically in the editor's actual scroll container
// (.editor-workspace -- #chapter_editor itself doesn't scroll, see
// index.css) rather than just barely exposing it at the top/bottom edge.
function scrollRangeIntoView(range: Range) {
  const rect = range.getClientRects()[0] ?? range.getBoundingClientRect()
  if (rect.width === 0 && rect.height === 0) return
  const anchor = range.commonAncestorContainer instanceof Element
    ? range.commonAncestorContainer
    : range.commonAncestorContainer.parentElement
  const container = anchor?.closest<HTMLElement>('.editor-workspace')
  if (!container) return
  const containerRect = container.getBoundingClientRect()
  const targetTop = rect.top - containerRect.top + container.scrollTop
  const desiredScrollTop = targetTop - container.clientHeight / 2 + rect.height / 2
  container.scrollTo({ top: Math.max(0, desiredScrollTop), behavior: 'smooth' })
}

// P1.2/P1.1A Journal "Write Today": appends a bold time paragraph plus an
// empty, immediately-editable paragraph after it, and leaves the caret in
// that empty paragraph. Ordinary <div> blocks (this editor's own paragraph
// unit -- see index.css's `#chapter_editor div` rule and
// setFirstLineIndent's comment on wrapping loose text the same way), no
// proprietary markers: the saved HTML reads and exports like any other
// chapter content. Only the time is shown (not the date, which the
// Chapter itself already represents) and never seconds.
//
// `timeLabel` arrives already formatted by the backend using the Book
// *owner's* journalTimeFormat preference (see JournalWriteTodayResult) --
// inserted verbatim, never reformatted client-side, so every collaborator's
// browser locale/settings can't produce a different-looking label for the
// same entry.
function appendJournalTimestamp(editor: HTMLDivElement, timeLabel: string): void {
  const timestampBlock = document.createElement('div')
  const strong = document.createElement('strong')
  strong.textContent = timeLabel
  timestampBlock.appendChild(strong)

  const editableBlock = document.createElement('div')
  editableBlock.appendChild(document.createElement('br'))

  editor.appendChild(timestampBlock)
  editor.appendChild(editableBlock)

  const selection = window.getSelection()
  const range = document.createRange()
  range.setStart(editableBlock, 0)
  range.collapse(true)
  selection?.removeAllRanges()
  selection?.addRange(range)
}

const SPECIAL_CHARACTERS = [
  ['—', 'Em dash'],
  ['–', 'En dash'],
  ['…', 'Ellipsis'],
  ['“', 'Opening double quote'],
  ['”', 'Closing double quote'],
  ['‘', 'Opening single quote'],
  ['’', 'Closing single quote'],
  ['•', 'Bullet'],
  ['§', 'Section'],
  ['¶', 'Paragraph'],
  ['°', 'Degree'],
  ['©', 'Copyright'],
  ['®', 'Registered'],
  ['™', 'Trademark'],
  ['£', 'Pound'],
  ['€', 'Euro'],
  ['é', 'E acute'],
  ['ñ', 'N tilde'],
] as const

function countWords(element: HTMLDivElement | null) {
  const text = element?.innerText.trim() ?? ''
  return text ? text.split(/\s+/).length : 0
}

function countPlainTextWords(text: string) {
  const trimmed = text.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

function execCmd(command: string, value?: string) {
  document.execCommand(command, false, value)
}

function internalReferenceIdentity(anchor: HTMLAnchorElement): {
  targetType: InternalReferenceTargetType
  targetId: string
} | null {
  const targetType = anchor.dataset.calwriterTargetType
  const targetId = anchor.dataset.calwriterTargetId
  if (!targetId || !['book', 'folder', 'chapter'].includes(targetType ?? '')) return null
  return { targetType: targetType as InternalReferenceTargetType, targetId }
}

/** Resolution state is presentation-only. Never persist a temporary
 * unavailable/resolving marker back into chapter content. */
function serializeEditorHtml(editor: HTMLDivElement | null): string {
  if (!editor) return ''
  const clone = editor.cloneNode(true) as HTMLDivElement
  for (const anchor of clone.querySelectorAll<HTMLAnchorElement>('a[data-calwriter-target-id]')) {
    anchor.removeAttribute('data-calwriter-status')
    anchor.removeAttribute('title')
  }
  return clone.innerHTML
}

/** How one contenteditable `input` event's DOM.InputEvent.inputType should
 * be treated for writing-activity purposes. Fail-closed by design: only an
 * explicit allowlist of genuine keyboard/composition inputTypes counts as
 * 'typed' -- an unrecognized inputType (a browser gap, a future spec
 * addition) falls to 'other' rather than defaulting to typed, since a
 * missed word is a much safer failure than fabricated goal/WPM credit.
 * Paste/drop aren't classified here -- their word counts come from the
 * clipboard/dataTransfer content directly (see ChapterEditor's onPaste/
 * onDrop), not from inputType, because a paste that replaces a selection
 * has a net word-count delta that differs from the pasted content's own
 * size (see the P0.2 spec's "select 100, paste 250" example). A pure,
 * exported function so this classification is unit-testable on its own. */
export type InputClassification = 'typed' | 'delete' | 'other'

const TYPED_INPUT_TYPES = new Set([
  'insertText',
  'insertReplacementText',
  'insertParagraph',
  'insertLineBreak',
  'insertCompositionText',
  'insertFromComposition',
])

export function classifyInputType(inputType: string | null | undefined): InputClassification {
  if (!inputType) return 'other'
  if (TYPED_INPUT_TYPES.has(inputType)) return 'typed'
  if (inputType.startsWith('delete')) return 'delete'
  return 'other'
}

function AlignmentIcon({ align }: { align: 'left' | 'center' | 'right' }) {
  const path = {
    left: 'M2 3h12M2 6.5h9M2 10h12M2 13.5h7',
    center: 'M2 3h12M3.5 6.5h9M2 10h12M4.5 13.5h7',
    right: 'M2 3h12M5 6.5h9M2 10h12M7 13.5h7',
  }[align]

  return (
    <svg className="alignment-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d={path} />
    </svg>
  )
}

function setFirstLineIndent(editor: HTMLDivElement, remove: boolean) {
  const selection = window.getSelection()
  if (!selection?.anchorNode || !editor.contains(selection.anchorNode)) return false

  const anchor = selection.anchorNode instanceof HTMLElement
    ? selection.anchorNode
    : selection.anchorNode.parentElement
  let paragraph = anchor?.closest<HTMLElement>('p, div') ?? null

  // Plain text can sit directly inside a contenteditable before the first
  // Enter. Wrap that line so text-indent applies to the paragraph rather than
  // to the entire editor.
  if (!paragraph || paragraph === editor) {
    document.execCommand('formatBlock', false, 'div')
    const updatedAnchor = window.getSelection()?.anchorNode
    const updatedElement = updatedAnchor instanceof HTMLElement
      ? updatedAnchor
      : updatedAnchor?.parentElement
    paragraph = updatedElement?.closest<HTMLElement>('p, div') ?? null
  }

  if (!paragraph || paragraph === editor || !editor.contains(paragraph)) return false
  const currentEm = parseFloat(paragraph.style.textIndent) || 0
  const nextEm = Math.max(0, currentEm + (remove ? -2 : 2))
  paragraph.style.textIndent = `${nextEm}em`
  return true
}

// True when the caret sits before any text in `block` -- checked by measuring
// the text between the block's start and the caret rather than comparing
// nodes/offsets directly, so it holds regardless of inline formatting
// elements (<b>, <i>, ...) or an empty <br> placeholder line.
function isCaretAtStartOfBlock(block: HTMLElement): boolean {
  const selection = window.getSelection()
  if (!selection?.rangeCount) return false
  const range = selection.getRangeAt(0)
  if (!range.collapsed) return false
  const preRange = document.createRange()
  preRange.selectNodeContents(block)
  preRange.setEnd(range.startContainer, range.startOffset)
  return preRange.toString().length === 0
}

// Closest <li> the caret sits in, if any -- Tab means "nest this list item"
// there, vs. "indent this paragraph's first line" everywhere else.
function closestListItem(editor: HTMLDivElement): HTMLLIElement | null {
  const anchor = window.getSelection()?.anchorNode
  const anchorEl = anchor instanceof HTMLElement ? anchor : anchor?.parentElement
  const li = anchorEl?.closest<HTMLLIElement>('li')
  return li && editor.contains(li) ? li : null
}

// Text from the start of `block` up to the caret -- used to recognize a
// markdown shortcut ("- ", "1. ", "[ ] ") typed at the start of a line.
function textBeforeCaretInBlock(block: HTMLElement): string {
  const selection = window.getSelection()
  if (!selection?.rangeCount) return ''
  const range = selection.getRangeAt(0)
  if (!range.collapsed) return ''
  const preRange = document.createRange()
  preRange.selectNodeContents(block)
  preRange.setEnd(range.startContainer, range.startOffset)
  return preRange.toString()
}

// Moving an <li> in the DOM doesn't reliably keep the caret inside it --
// especially when it's empty (just a <br> placeholder), the browser tends
// to lose track and silently leave the caret wherever it happened to end up
// after the mutation, so a second Tab press acts on the wrong item entirely.
// Restores the caret at the end of the item's own content, i.e. right
// before any nested sublist rather than inside it.
function placeCaretAtEndOfOwnContent(li: HTMLElement) {
  const selection = window.getSelection()
  if (!selection) return
  const range = document.createRange()
  const nested = Array.from(li.children).find((c) => c.tagName === 'UL' || c.tagName === 'OL')
  if (nested) {
    range.setStartBefore(nested)
    range.collapse(true)
  } else {
    range.selectNodeContents(li)
    range.collapse(false)
  }
  selection.removeAllRanges()
  selection.addRange(range)
}

// Chromium's execCommand('indent'/'outdent') turned out unusable for nested
// lists: indent nests a list as a *sibling* of the <li> it followed instead
// of inside it, and outdent is worse -- on a selection several levels deep
// it sometimes outdented a *different*, unrelated top-level item instead of
// the one the caret was in. Rather than fight the browser's own notion of
// "indent" (which can't be corrected after the fact, since it already chose
// the wrong node), both are implemented directly as plain DOM moves.

// Nests `li` under its immediately preceding sibling, creating a sublist
// there if one doesn't already exist. No-op (returns false) for the first
// item in a list -- there's nothing to nest it under.
function indentListItem(li: HTMLLIElement): boolean {
  const prevLi = li.previousElementSibling
  if (!prevLi || prevLi.tagName !== 'LI') return false
  const list = li.parentElement
  if (!list) return false
  let sublist = Array.from(prevLi.children).find((c) => c.tagName === 'UL' || c.tagName === 'OL') as
    | HTMLElement
    | undefined
  if (!sublist) {
    sublist = document.createElement(list.tagName.toLowerCase())
    prevLi.appendChild(sublist)
  }
  sublist.appendChild(li)
  placeCaretAtEndOfOwnContent(li)
  return true
}

// Moves `li` up to be a sibling of the <li> its list is nested inside. Any
// siblings after `li` in its current list move with it, becoming its own
// new sublist (so outdenting item 2 of [2, 3, 4] doesn't strand 3 and 4
// behind at the old depth). No-op (returns false) at the top level.
function outdentListItem(li: HTMLLIElement): boolean {
  const list = li.parentElement
  if (!list) return false
  const parentLi = list.parentElement
  if (!parentLi || parentLi.tagName !== 'LI') return false
  const grandList = parentLi.parentElement
  if (!grandList) return false

  const laterSiblings: Element[] = []
  for (let sib = li.nextElementSibling; sib; ) {
    const next: Element | null = sib.nextElementSibling
    laterSiblings.push(sib)
    sib = next
  }
  if (laterSiblings.length > 0) {
    const subList = document.createElement(list.tagName.toLowerCase())
    for (const s of laterSiblings) subList.appendChild(s)
    li.appendChild(subList)
  }

  grandList.insertBefore(li, parentLi.nextElementSibling)
  if (list.children.length === 0) list.remove()
  placeCaretAtEndOfOwnContent(li)
  return true
}

// Caret/selection position expressed as plain-text character offsets from
// the start of the editor, counting through every descendant text node in
// document order (the same counting Range.toString().length already uses
// elsewhere in this file -- see isCaretAtStartOfBlock/textBeforeCaretInBlock).
// A history snapshot's DOM is thrown away and rebuilt wholesale on
// undo/redo (editor.innerHTML = ...), which invalidates any node reference
// a Range could hold -- an offset survives that because it's recomputed
// against whatever nodes exist post-restore instead of pointing at ones
// that no longer do.
type HistorySelection = { start: number; end: number }

function captureHistorySelection(editor: HTMLDivElement): HistorySelection | null {
  const selection = window.getSelection()
  if (!selection?.rangeCount) return null
  const range = selection.getRangeAt(0)
  if (!editor.contains(range.commonAncestorContainer)) return null
  const preStart = document.createRange()
  preStart.selectNodeContents(editor)
  preStart.setEnd(range.startContainer, range.startOffset)
  const preEnd = document.createRange()
  preEnd.selectNodeContents(editor)
  preEnd.setEnd(range.endContainer, range.endOffset)
  return { start: preStart.toString().length, end: preEnd.toString().length }
}

function resolveHistoryOffset(editor: HTMLDivElement, targetOffset: number): { node: Node; offset: number } {
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT)
  let remaining = targetOffset
  let lastText: Text | null = null
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node as Text
    lastText = text
    if (remaining <= text.data.length) return { node: text, offset: remaining }
    remaining -= text.data.length
  }
  return lastText ? { node: lastText, offset: lastText.data.length } : { node: editor, offset: 0 }
}

function restoreHistorySelection(editor: HTMLDivElement, sel: HistorySelection | null) {
  if (!sel) return
  const selection = window.getSelection()
  if (!selection) return
  const start = resolveHistoryOffset(editor, sel.start)
  const end = resolveHistoryOffset(editor, sel.end)
  const range = document.createRange()
  range.setStart(start.node, start.offset)
  range.setEnd(end.node, end.offset)
  selection.removeAllRanges()
  selection.addRange(range)
}

function clearBlockText(block: HTMLElement) {
  const selection = window.getSelection()
  if (!selection) return
  const range = document.createRange()
  range.selectNodeContents(block)
  selection.removeAllRanges()
  selection.addRange(range)
  document.execCommand('delete')
}

// Ctrl/Cmd+Z, Shift+Z, and Y are intercepted earlier, directly in
// ChapterEditor's onKeyDown (see performUndo/performRedo there) -- undo/redo
// no longer goes through document.execCommand at all, so there's nothing
// for this module-level handler to do for those keys.
function handleEditorKeyDown(e: KeyboardEvent<HTMLDivElement>, withHistoryCommit: (mutate: () => void) => void) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const li = closestListItem(e.currentTarget)
    if (li) {
      let changed = false
      withHistoryCommit(() => {
        changed = e.shiftKey ? outdentListItem(li) : indentListItem(li)
      })
      return changed
    }
    let changed = false
    withHistoryCommit(() => {
      changed = setFirstLineIndent(e.currentTarget, e.shiftKey)
    })
    return changed
  }
  if (e.key === 'Backspace' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const editor = e.currentTarget
    const anchor = window.getSelection()?.anchorNode
    const anchorEl = anchor instanceof HTMLElement ? anchor : anchor?.parentElement
    const block = anchorEl?.closest<HTMLElement>('p, div')
    if (block && block !== editor && editor.contains(block) && (parseFloat(block.style.textIndent) || 0) > 0) {
      if (isCaretAtStartOfBlock(block)) {
        e.preventDefault()
        let changed = false
        withHistoryCommit(() => {
          changed = setFirstLineIndent(editor, true)
        })
        return changed
      }
    }
  }
  // Chrome applies bold/italic/underline natively for these combos on any
  // contenteditable, but Firefox reserves Ctrl+B (bookmarks sidebar) and
  // Ctrl+U (view source) as browser-chrome shortcuts and never hands them to
  // the page -- so they have to be handled explicitly and preventDefault'd
  // here to work consistently across browsers.
  if (!e.ctrlKey && !e.metaKey) return
  switch (e.key.toLowerCase()) {
    case 'b':
      e.preventDefault()
      withHistoryCommit(() => execCmd('bold'))
      return false
    case 'i':
      e.preventDefault()
      withHistoryCommit(() => execCmd('italic'))
      return false
    case 'u':
      e.preventDefault()
      withHistoryCommit(() => execCmd('underline'))
      return false
  }
  return false
}

export default function ChapterEditor({
  chapterId,
  initialHtml,
  onChange,
  onWordCountChange,
  onActivity,
  onTypingInput,
  bookColor,
  writeMode,
  onToggleWriteMode,
  completed,
  onToggleComplete,
  onNavigateInternalReference,
  findRequest,
  onFindHandled,
  journalEntryRequest,
  onJournalEntryHandled,
}: {
  chapterId: string
  initialHtml: string
  onChange: (html: string) => void
  onWordCountChange?: (count: number) => void
  /** Fired whenever an edit earns writing-activity credit, classified at
   * the source -- see classifyInputType. A genuine keyboard/composition
   * edit's word-count delta reports typedWords when positive or
   * deletedWords (as a positive count) when negative -- never both in one
   * call, and neither when the delta is zero (e.g. "cat" -> "car"; see
   * onTypingInput for that case). Content actually brought in via clipboard
   * paste or an external drop reports pastedWords instead, independent of
   * net word-count delta -- pasting 250 words over a 100-word selection
   * reports pastedWords: 250, not the net +150, and never touches
   * typedWords/deletedWords. Undo/redo never fires this at all. */
  onActivity?: (delta: { typedWords: number; pastedWords: number; deletedWords: number }) => void
  /** Fired for genuine keyboard/composition input (including deletes) even
   * when it doesn't change word count -- e.g. "cat" -> "car". This is the
   * signal active-writing-time should gate on, deliberately separate from
   * onChange (which also fires for paste/formatting/programmatic edits)
   * and from onActivity (which only fires on a word-count-affecting typed
   * edit or a paste). */
  onTypingInput?: () => void
  /** Resolved book color to tint the editor background with, or null/undefined
   * to leave the editor at its plain theme background. */
  bookColor?: string | null
  /** Distraction-free mode: hides the app sidebar plus everything above this
   * toolbar (chapter tabs, header) -- driven by the parent ChapterPage since
   * that's what owns the tabs/header being hidden. */
  writeMode: boolean
  onToggleWriteMode: () => void
  /** Chapter's own completed_at !== null -- surfaced here too (also settable
   * from Chapter Settings and the Book/Folder chapter list) so marking a
   * chapter done doesn't require leaving the editor. Optional since not
   * every caller of this component (there is only one today, ChapterPage)
   * necessarily has permission to toggle it. */
  completed?: boolean
  onToggleComplete?: () => void
  onNavigateInternalReference: (route: string) => void
  /** Search 2.0 (P1.1) jump-to-occurrence handoff -- ChapterPage derives
   * this from the chapter URL's find/findSource/findIndex params (content
   * source only; a notes match is handled directly by ChapterPage against
   * the notes textarea, never passed here). The occurrence is re-located
   * by re-running the same literal search against the *current* live
   * content rather than trusting stale offsets from whenever the user
   * searched -- see findLiteralOccurrences/canonicalSearchText. */
  findRequest?: { query: string; occurrenceIndex: number } | null
  /** Fired once per findRequest, true if the occurrence was found and
   * highlighted, false if the chapter has changed since and it no longer
   * exists (a stale result) -- either way ChapterPage should clear the
   * temporary find params from the URL. */
  onFindHandled?: (found: boolean) => void
  /** P1.2/P1.1A Journal "Write Today" timestamp handoff -- ChapterPage
   * derives this from the chapter URL's journalEntry/journalEntryTimeLabel
   * params. `requestId` is consumed exactly once (tracked internally),
   * making repeated deliveries of the same request -- Strict Mode, an
   * effect rerun, a Chapter refetch -- safe no-ops instead of a second
   * timestamp. `timeLabel` is the Book owner's journalTimeFormat-formatted
   * label (e.g. "10:42 PM"/"22:42") from JournalWriteTodayResult, inserted
   * verbatim -- never reformatted client-side. */
  journalEntryRequest?: { requestId: string; timeLabel: string } | null
  /** Fired once the journalEntryRequest has been applied (or skipped as
   * already-consumed) so ChapterPage can clear the temporary URL params. */
  onJournalEntryHandled?: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const characterPickerRef = useRef<HTMLDivElement>(null)
  const lastLoadedChapterId = useRef<string | null>(null)
  // P1.2: the last journalEntryRequest.requestId actually applied -- guards
  // against inserting a second timestamp for the same Write Today click via
  // Strict Mode's double effect invocation, an unrelated rerender, or a
  // Chapter refetch re-delivering the same (still-unconsumed-per-URL) props.
  const consumedJournalRequestIdRef = useRef<string | null>(null)
  // Word count as of the last processed mutation -- lets the onInput
  // classifier compute a typed delta regardless of which code path last
  // changed the DOM (toolbar command, markdown shortcut, raw typing, ...).
  // Always kept in sync via reportWordCount below, never written directly.
  const lastWordCountRef = useRef(0)
  // Word count of the most recent paste/external-drop's own clipboard/
  // dataTransfer plain text, set by onPaste/onDrop and consumed by the
  // very next onInput event (insertFromPaste/insertFromDrop) -- this is
  // what lets "pasted words" reflect the clipboard content's own size
  // rather than the net word-count delta (see onActivity's docstring).
  const pendingPasteWordsRef = useRef(0)
  // True from onDragStart until onDrop/onDragEnd -- distinguishes an
  // internal drag (reordering a paragraph within this same editor, which
  // must not count as "words pasted") from a drop of external content.
  const internalDragActiveRef = useRef(false)
  // Set by runCommand (the toolbar-button helper) just before invoking
  // execCommand, and consumed by the very next onInput event. This is what
  // stops a programmatic execCommand call that happens to produce an
  // inputType the classifier would otherwise treat as typing (e.g. the
  // special-character picker's execCommand('insertText', char)) from being
  // indistinguishable from real keyboard input.
  const pendingSourceOverrideRef = useRef<'programmatic' | null>(null)
  const savedLinkRangeRef = useRef<Range | null>(null)
  // The one coherent edit history -- see the module-level comment on
  // TYPING_HISTORY_COALESCE_MS. historyRef[historyIndexRef] is always kept
  // equal to the editor's current (serialized) content whenever no
  // keystroke/operation is in flight; commitHistorySnapshot is what
  // maintains that invariant. Refs, not state -- committed on every
  // keystroke's debounce, which is far too often to route through React.
  const historyRef = useRef<{ html: string; selection: HistorySelection | null }[]>([])
  const historyIndexRef = useRef(0)
  const typingCommitTimerRef = useRef<number | null>(null)
  // Nesting guard for withHistoryCommit: a markdown shortcut's clearBlockText
  // + applyChecklist(...) call is one user-facing operation even though
  // applyChecklist independently wraps itself for its own (toolbar-button)
  // call site -- without this, the inner call's flush/commit would split
  // that one operation into two history entries. Only depth 0 -> 1 flushes
  // the prior state and only 1 -> 0 commits the result; everything in
  // between collapses into that single outer entry.
  const historyCommitDepthRef = useRef(0)

  function commitHistorySnapshot() {
    const editor = ref.current
    if (!editor) return
    const html = serializeEditorHtml(editor)
    const top = historyRef.current[historyIndexRef.current]
    if (top && top.html === html) return
    const entries = [
      ...historyRef.current.slice(0, historyIndexRef.current + 1),
      { html, selection: captureHistorySelection(editor) },
    ]
    if (entries.length > HISTORY_LIMIT) entries.shift()
    historyRef.current = entries
    historyIndexRef.current = entries.length - 1
  }

  function flushTypingHistoryCommit() {
    if (typingCommitTimerRef.current !== null) {
      window.clearTimeout(typingCommitTimerRef.current)
      typingCommitTimerRef.current = null
    }
    commitHistorySnapshot()
  }

  // Debounced entry point for genuine native input events (typing, deleting,
  // paste, drop, ...) -- called unconditionally from onInput. Coalesces a
  // burst of keystrokes into one history entry per pause, rather than one
  // per character. Safe to call even for a DOM change that a withHistoryCommit
  // call already committed synchronously (e.g. a toolbar click, whose
  // execCommand triggers this same onInput handler) -- commitHistorySnapshot's
  // no-op check means the eventual timer firing just finds nothing new.
  function scheduleTypingHistoryCommit() {
    if (typingCommitTimerRef.current !== null) window.clearTimeout(typingCommitTimerRef.current)
    typingCommitTimerRef.current = window.setTimeout(() => {
      typingCommitTimerRef.current = null
      commitHistorySnapshot()
    }, TYPING_HISTORY_COALESCE_MS)
  }

  // Wraps a programmatic/structural DOM mutation (list conversion,
  // indent/outdent, checklist toggle, link, toolbar command, ...) so it
  // becomes its own atomic, undoable history entry: whatever was pending
  // from typing is flushed as its own entry first, the mutation runs, then
  // its result is committed as the next entry.
  function withHistoryCommit(mutate: () => void) {
    if (historyCommitDepthRef.current === 0) flushTypingHistoryCommit()
    historyCommitDepthRef.current += 1
    try {
      mutate()
    } finally {
      historyCommitDepthRef.current -= 1
      if (historyCommitDepthRef.current === 0) commitHistorySnapshot()
    }
  }

  function restoreHistoryEntry(entry: { html: string; selection: HistorySelection | null }) {
    const editor = ref.current
    if (!editor) return
    editor.innerHTML = entry.html
    editor.focus()
    restoreHistorySelection(editor, entry.selection)
    refreshInternalReferences(editor)
    // Undo/redo must earn no typed/pasted/goal/streak/WPM credit -- only the
    // normal content-change/reporting paths (autosave, word count), never
    // onActivity/onTypingInput.
    onChange(serializeEditorHtml(editor))
    reportWordCount(countWords(editor))
  }

  // Both flush first: an in-flight (not-yet-debounced) typing burst must
  // become its own entry before moving the history pointer, both so undo
  // removes exactly that burst (not silently discarding it unrecorded) and
  // so redo's "stale future" is correctly invalidated by the flush's own
  // commit (which truncates historyRef past the current index) rather than
  // by performRedo finding a redo target that new typing already made stale.
  function performUndo() {
    flushTypingHistoryCommit()
    if (historyIndexRef.current <= 0) return
    historyIndexRef.current -= 1
    restoreHistoryEntry(historyRef.current[historyIndexRef.current])
  }

  function performRedo() {
    flushTypingHistoryCommit()
    if (historyIndexRef.current >= historyRef.current.length - 1) return
    historyIndexRef.current += 1
    restoreHistoryEntry(historyRef.current[historyIndexRef.current])
  }
  const [showCharacters, setShowCharacters] = useState(false)
  const [linkSelection, setLinkSelection] = useState<string | null>(null)
  const [linkSelectionError, setLinkSelectionError] = useState(false)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const { open: openShortcuts } = useShortcutsModal()
  const [isFullWidth, setIsFullWidth] = useState(() => {
    try {
      return localStorage.getItem(FULL_WIDTH_KEY) === 'true'
    } catch {
      return false
    }
  })

  function reportWordCount(count: number) {
    lastWordCountRef.current = count
    onWordCountChange?.(count)
  }

  async function copyAllText() {
    const text = ref.current?.innerText ?? ''
    setCopyStatus((await copyText(text)) ? 'copied' : 'error')
    setTimeout(() => setCopyStatus('idle'), 2000)
  }

  async function resolveInternalReference(anchor: HTMLAnchorElement) {
    const identity = internalReferenceIdentity(anchor)
    if (!identity) return null
    anchor.dataset.calwriterStatus = 'resolving'
    try {
      const resolved = await api.get<InternalReferenceResolution>(
        `/internal-references/${identity.targetType}/${encodeURIComponent(identity.targetId)}`,
      )
      if (anchor.isConnected) {
        anchor.dataset.calwriterStatus = 'available'
        anchor.title = `${resolved.name} — open ${resolved.targetType}`
      }
      return resolved
    } catch {
      if (anchor.isConnected) {
        anchor.dataset.calwriterStatus = 'unavailable'
        anchor.title = 'Reference unavailable'
      }
      return null
    }
  }

  function refreshInternalReferences(editor: HTMLDivElement) {
    for (const anchor of editor.querySelectorAll<HTMLAnchorElement>('a[data-calwriter-target-id]')) {
      void resolveInternalReference(anchor)
    }
  }

  // Only set innerHTML when we switch chapters, never on every render --
  // otherwise React would clobber the cursor position on each keystroke.
  useEffect(() => {
    if (ref.current && lastLoadedChapterId.current !== chapterId) {
      ref.current.innerHTML = initialHtml
      lastLoadedChapterId.current = chapterId
      reportWordCount(countWords(ref.current))
      // A chapter switch is a new editing session -- none of these should
      // carry over and get attributed to the newly-loaded chapter.
      pendingPasteWordsRef.current = 0
      internalDragActiveRef.current = false
      pendingSourceOverrideRef.current = null
      refreshInternalReferences(ref.current)
      // A different chapter's edit history has nothing to do with this
      // one's -- start fresh at this chapter's own loaded content, and drop
      // any in-flight coalescing timer from whatever chapter was open before.
      if (typingCommitTimerRef.current !== null) {
        window.clearTimeout(typingCommitTimerRef.current)
        typingCommitTimerRef.current = null
      }
      historyRef.current = [{ html: serializeEditorHtml(ref.current), selection: null }]
      historyIndexRef.current = 0
      historyCommitDepthRef.current = 0
      // A leftover highlight from whatever chapter was open before would
      // otherwise keep pointing at now-detached DOM.
      clearSearchHighlight()
      consumedJournalRequestIdRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId, initialHtml, onWordCountChange])

  // Search 2.0 (P1.1) jump-to-occurrence: re-locates the requested
  // occurrence against the *current* live content (not trusting whatever
  // offsets existed when the user searched -- see findRequest's docstring)
  // and highlights + scrolls to it. Runs after the chapter-load effect
  // above in the same commit on a fresh mount, so the editor's content is
  // already in the DOM by the time this reads it.
  useEffect(() => {
    if (!findRequest || !ref.current) return
    const editor = ref.current
    const occurrences = findLiteralOccurrences(canonicalSearchText(editor), findRequest.query)
    const span = occurrences[findRequest.occurrenceIndex]
    const range = span ? rangeForCanonicalOffsets(editor, span[0], span[1]) : null
    if (!range) {
      onFindHandled?.(false)
      return
    }
    applySearchHighlight(range)
    scrollRangeIntoView(range)
    onFindHandled?.(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findRequest, chapterId])

  // Leaving the Chapter page entirely (not just switching chapters, which
  // the chapter-load effect above already handles) must not leave a
  // highlight registered against a now-unmounted editor.
  useEffect(() => clearSearchHighlight, [])

  // P1.2 Journal "Write Today" timestamp handoff. requestId-guarded so
  // Strict Mode's double effect invocation, an unrelated rerender, or a
  // Chapter refetch that redelivers the same (still-unconsumed-per-URL)
  // props can never append a second timestamp for one Write Today click --
  // "exactly once," not a time-based suppression window. The insertion
  // itself is a plain DOM mutation (append two <div>s), not execCommand or
  // a real keystroke, so it never fires onInput -- meaning it earns no
  // typed/pasted/deleted/WPM/goal credit unless this code explicitly grants
  // it, which it deliberately never does. It still must call the normal
  // content-change/reporting paths itself afterward (onChange/
  // reportWordCount), same as every other direct-DOM list/checklist
  // operation in this file, and it's wrapped in withHistoryCommit so
  // Undo/Redo treats the whole insertion as one atomic step.
  useEffect(() => {
    if (!journalEntryRequest || !ref.current) return
    if (consumedJournalRequestIdRef.current === journalEntryRequest.requestId) return
    consumedJournalRequestIdRef.current = journalEntryRequest.requestId
    const editor = ref.current
    withHistoryCommit(() => {
      appendJournalTimestamp(editor, journalEntryRequest.timeLabel)
    })
    onChange(serializeEditorHtml(editor))
    reportWordCount(countWords(editor))
    const container = editor.closest<HTMLElement>('.editor-workspace')
    container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    editor.focus()
    onJournalEntryHandled?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journalEntryRequest, chapterId])

  useEffect(() => {
    if (!showCharacters) return

    function closePicker(e: MouseEvent) {
      if (!characterPickerRef.current?.contains(e.target as Node)) setShowCharacters(false)
    }
    function closePickerWithEscape(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') setShowCharacters(false)
    }

    document.addEventListener('mousedown', closePicker)
    document.addEventListener('keydown', closePickerWithEscape)
    return () => {
      document.removeEventListener('mousedown', closePicker)
      document.removeEventListener('keydown', closePickerWithEscape)
    }
  }, [showCharacters])

  function runCommand(command: string, value?: string) {
    // Every toolbar-button command runs through here (this is the only
    // execCommand call site reachable from a click rather than raw
    // keystrokes) -- flagging it 'programmatic' up front stops e.g. the
    // special-character picker's execCommand('insertText', char) from
    // being indistinguishable from genuine typing to the onInput
    // classifier, which would otherwise see the exact same 'insertText'
    // inputType either way.
    withHistoryCommit(() => {
      pendingSourceOverrideRef.current = 'programmatic'
      execCmd(command, value)
    })
    ref.current?.focus()
    onChange(serializeEditorHtml(ref.current))
    reportWordCount(countWords(ref.current))
  }

  function runParagraphIndent(remove: boolean) {
    withHistoryCommit(() => {
      if (ref.current && setFirstLineIndent(ref.current, remove)) {
        onChange(serializeEditorHtml(ref.current))
      }
    })
    ref.current?.focus()
  }

  // Marks the list item(s) touched by the current selection as checklist
  // items (creating a list first if the caret isn't in one yet), so both
  // the toolbar button and the "[] "/"[x] " markdown shortcuts share one
  // implementation. Falls back to just the caret's own item when nothing
  // in the current selection intersects an <li> (e.g. a collapsed caret in
  // freshly-created list markup, before layout has settled).
  function applyChecklist(checked: boolean) {
    const editor = ref.current
    if (!editor) return
    editor.focus()
    withHistoryCommit(() => {
      if (!closestListItem(editor)) {
        // Only set the override immediately before an execCommand call that
        // will actually happen -- an unconsumed override would otherwise
        // wrongly swallow the next real keystroke's typed credit.
        pendingSourceOverrideRef.current = 'programmatic'
        execCmd('insertUnorderedList')
      }
      const selection = window.getSelection()
      const range = selection?.rangeCount ? selection.getRangeAt(0) : null
      const allItems = Array.from(editor.querySelectorAll('li'))
      const affected = range ? allItems.filter((li) => range.intersectsNode(li)) : []
      const current = closestListItem(editor)
      const targets = affected.length > 0 ? affected : current ? [current] : []
      for (const li of targets) {
        li.classList.add('checklist-item')
        li.classList.toggle('checked', checked)
      }
    })
    onChange(serializeEditorHtml(editor))
    reportWordCount(countWords(editor))
  }

  // Converts "- "/"* " to a bullet list, "1. " to a numbered list, and
  // "[] "/"[x] " to a checklist item -- but only when that's *all* the
  // block contains so far, so it only fires when starting a fresh line
  // with markdown syntax, never mid-sentence.
  function handleMarkdownShortcut(e: KeyboardEvent<HTMLDivElement>): boolean {
    const editor = e.currentTarget
    const anchor = window.getSelection()?.anchorNode
    const anchorEl = anchor instanceof HTMLElement ? anchor : anchor?.parentElement
    const block = anchorEl?.closest<HTMLElement>('p, div, li')
    if (!block || !editor.contains(block)) return false
    const text = textBeforeCaretInBlock(block)

    if (/^[-*]$/.test(text)) {
      e.preventDefault()
      withHistoryCommit(() => {
        clearBlockText(block)
        pendingSourceOverrideRef.current = 'programmatic'
        execCmd('insertUnorderedList')
      })
      onChange(serializeEditorHtml(editor))
      reportWordCount(countWords(editor))
      return true
    }
    if (/^\d+\.$/.test(text)) {
      e.preventDefault()
      withHistoryCommit(() => {
        clearBlockText(block)
        pendingSourceOverrideRef.current = 'programmatic'
        execCmd('insertOrderedList')
      })
      onChange(serializeEditorHtml(editor))
      reportWordCount(countWords(editor))
      return true
    }
    if (/^\[ ?\]$/.test(text)) {
      e.preventDefault()
      withHistoryCommit(() => {
        clearBlockText(block)
        applyChecklist(false)
      })
      return true
    }
    if (/^\[[xX]\]$/.test(text)) {
      e.preventDefault()
      withHistoryCommit(() => {
        clearBlockText(block)
        applyChecklist(true)
      })
      return true
    }
    return false
  }

  function toggleEditorWidth() {
    setIsFullWidth((fullWidth) => {
      const next = !fullWidth
      try {
        localStorage.setItem(FULL_WIDTH_KEY, String(next))
      } catch {
        // The preference can remain session-only if storage is unavailable.
      }
      return next
    })
  }

  function openLinkDialog() {
    const editor = ref.current
    const selection = window.getSelection()
    if (!editor || !selection?.rangeCount) return
    const range = selection.getRangeAt(0)
    if (range.collapsed || !editor.contains(range.commonAncestorContainer) || !range.toString().trim()) {
      setLinkSelectionError(true)
      setTimeout(() => setLinkSelectionError(false), 2200)
      return
    }
    savedLinkRangeRef.current = range.cloneRange()
    setLinkSelection(range.toString().trim())
    setLinkSelectionError(false)
  }

  function applyLink(href: string, target?: InternalReferenceTarget) {
    const editor = ref.current
    const range = savedLinkRangeRef.current
    const selection = window.getSelection()
    if (!editor || !range || !selection || !editor.contains(range.commonAncestorContainer)) {
      setLinkSelection(null)
      savedLinkRangeRef.current = null
      return
    }
    editor.focus()
    selection.removeAllRanges()
    selection.addRange(range)
    withHistoryCommit(() => {
      pendingSourceOverrideRef.current = 'programmatic'
      execCmd('createLink', href)

      const selectionNode = selection.anchorNode
      const selectionElement = selectionNode instanceof HTMLElement ? selectionNode : selectionNode?.parentElement
      const anchor = selectionElement?.closest<HTMLAnchorElement>('a') ?? null
      if (anchor && editor.contains(anchor)) {
        if (target) {
          anchor.dataset.calwriterTargetType = target.targetType
          anchor.dataset.calwriterTargetId = target.targetId
          anchor.href = `calwriter://${target.targetType}/${target.targetId}`
          anchor.dataset.calwriterStatus = 'available'
          anchor.title = `${target.name} — open ${target.targetType}`
        } else {
          anchor.target = '_blank'
          anchor.rel = 'noopener noreferrer'
        }
      }
    })
    onChange(serializeEditorHtml(editor))
    reportWordCount(countWords(editor))
    pendingSourceOverrideRef.current = null
    savedLinkRangeRef.current = null
    setLinkSelection(null)
  }

  const tintStyle = bookColor
    ? ({ '--book-tint': `color-mix(in srgb, ${bookColor} 8%, var(--editor-bg))` } as CSSProperties)
    : undefined

  return (
    <div className={`chapter-editor-shell${isFullWidth ? ' full-width' : ''}`} style={tintStyle}>
      <div className="toolbar" role="toolbar" aria-label="Editor toolbar">
        <button type="button" className="icon-btn icon-bold" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('bold')} title="Bold (Ctrl+B)" aria-label="Bold" />
        <button type="button" className="icon-btn icon-italic" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('italic')} title="Italic (Ctrl+I)" aria-label="Italic" />
        <button type="button" className="icon-btn icon-underline" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('underline')} title="Underline (Ctrl+U)" aria-label="Underline" />
        <span className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="icon-btn icon-indent" onMouseDown={(e) => e.preventDefault()} onClick={() => runParagraphIndent(false)} title="Indent first line (Tab)" aria-label="Indent first line" />
        <button type="button" className="icon-btn icon-unindent" onMouseDown={(e) => e.preventDefault()} onClick={() => runParagraphIndent(true)} title="Remove first-line indent (Shift+Tab)" aria-label="Remove first-line indent" />
        <span className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="icon-btn icon-bulleted-list" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('insertUnorderedList')} title="Bulleted list" aria-label="Bulleted list" />
        <button type="button" className="icon-btn icon-numbered-list" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('insertOrderedList')} title="Numbered list" aria-label="Numbered list" />
        <button type="button" className="icon-btn icon-checklist" onMouseDown={(e) => e.preventDefault()} onClick={() => applyChecklist(false)} title="Checklist" aria-label="Checklist" />
        <span className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="icon-btn" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('justifyLeft')} title="Align left" aria-label="Align left"><AlignmentIcon align="left" /></button>
        <button type="button" className="icon-btn" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('justifyCenter')} title="Center" aria-label="Center"><AlignmentIcon align="center" /></button>
        <button type="button" className="icon-btn" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('justifyRight')} title="Align right" aria-label="Align right"><AlignmentIcon align="right" /></button>
        <span className="toolbar-divider" aria-hidden="true" />
        <button
          type="button"
          className="icon-btn icon-link"
          onMouseDown={(e) => e.preventDefault()}
          onClick={openLinkDialog}
          title="Link selected text"
          aria-label="Link selected text"
        />
        {linkSelectionError && <span className="link-selection-error">Select text first</span>}
        <span className="toolbar-divider" aria-hidden="true" />
        <div className="special-character-control" ref={characterPickerRef}>
          <button
            type="button"
            className={`icon-btn character-picker-trigger${showCharacters ? ' active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setShowCharacters((visible) => !visible)}
            aria-expanded={showCharacters}
            aria-haspopup="menu"
            title="Insert special character"
            aria-label="Insert special character"
          >
            Ω
          </button>
          {showCharacters && (
            <div className="special-character-menu" role="menu" aria-label="Special characters">
              <div className="special-character-menu-title">Insert character</div>
              <div className="special-character-grid">
                {SPECIAL_CHARACTERS.map(([character, label]) => (
                  <button
                    key={label}
                    type="button"
                    className="special-character-option"
                    role="menuitem"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      runCommand('insertText', character)
                      setShowCharacters(false)
                    }}
                    title={label}
                  >
                    <span>{character}</span>
                    <small>{label}</small>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <span className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="icon-btn icon-hr" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('insertHorizontalRule')} title="Horizontal line" aria-label="Insert horizontal line" />
        <span className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="icon-btn icon-undo" onMouseDown={(e) => e.preventDefault()} onClick={() => performUndo()} title="Undo (Ctrl+Z)" aria-label="Undo" />
        <button type="button" className="icon-btn icon-redo" onMouseDown={(e) => e.preventDefault()} onClick={() => performRedo()} title="Redo (Ctrl+Y)" aria-label="Redo" />
        <span className="toolbar-divider" aria-hidden="true" />
        <button
          type="button"
          className="icon-btn icon-shortcuts"
          onMouseDown={(e) => e.preventDefault()}
          onClick={openShortcuts}
          title="Keyboard shortcuts (Ctrl+/)"
          aria-label="Keyboard shortcuts"
        >
          ?
        </button>
        {onToggleComplete && (
          <>
            <span className="toolbar-divider" aria-hidden="true" />
            <button
              type="button"
              className={`icon-btn icon-complete${completed ? ' active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={onToggleComplete}
              aria-pressed={completed}
              title={completed ? 'Marked complete -- click to unmark' : 'Mark chapter complete'}
              aria-label={completed ? 'Marked complete -- click to unmark' : 'Mark chapter complete'}
            />
          </>
        )}
        <span className="toolbar-spacer" />
        <button
          type="button"
          className="editor-width-toggle"
          onClick={copyAllText}
          title="Copy all chapter text"
        >
          {copyStatus === 'copied' ? 'Copied!' : copyStatus === 'error' ? 'Copy failed' : 'Copy all'}
        </button>
        <button
          type="button"
          className={`editor-width-toggle${writeMode ? ' active' : ''}`}
          onClick={onToggleWriteMode}
          aria-pressed={writeMode}
          title="Hide the sidebar and everything above this toolbar"
        >
          Write Mode
        </button>
        <button
          type="button"
          className="editor-width-toggle"
          onClick={toggleEditorWidth}
          aria-pressed={isFullWidth}
          title={isFullWidth ? 'Use page width' : 'Use full width'}
        >
          {isFullWidth ? 'Page width' : 'Full width'}
        </button>
      </div>
      <div className="editor-workspace">
        <div
          id="chapter_editor"
          ref={ref}
          contentEditable
          suppressContentEditableWarning
          onInput={(e) => {
            // Search 2.0: a temporary jump-to-occurrence highlight is
            // presentation-only and lasts "until the user clicks/types in
            // the editor" -- any genuine input event ends it.
            clearSearchHighlight()
            const editor = ref.current
            if (editor) {
              const li = closestListItem(editor)
              if (li && !li.classList.contains('checklist-item')) {
                // Enter inside a checklist item creates a new <li> the
                // browser knows nothing about our "checklist-item" class --
                // carry it over (from whichever neighbor it split from) so
                // the new line keeps its checkbox instead of reverting to a
                // plain list marker. Checked per-sibling, not per-list, so
                // a checklist item can sit next to plain list items too.
                const fromNeighbor =
                  li.previousElementSibling?.classList.contains('checklist-item') ||
                  li.nextElementSibling?.classList.contains('checklist-item')
                if (fromNeighbor) li.classList.add('checklist-item')
              }
              // The browser also carries "checked" over from the item it
              // split off from, which isn't wanted -- a fresh item should
              // start unchecked. Only strip it while still empty, so this
              // doesn't undo an intentional checked-then-cleared edit.
              if (li?.classList.contains('checked') && !li.textContent?.trim()) {
                li.classList.remove('checked')
              }
            }
            const prevCount = lastWordCountRef.current
            const newCount = countWords(editor)
            onChange(serializeEditorHtml(editor))
            reportWordCount(newCount)
            // Every genuine input event -- typed, deleted, pasted, dropped,
            // or an unrecognized inputType -- schedules a (debounced,
            // coalescing) history commit. Safe to call even when a
            // withHistoryCommit call already committed this same DOM change
            // synchronously (e.g. a toolbar command's execCommand triggers
            // this handler too): commitHistorySnapshot no-ops when nothing's
            // changed since the last entry.
            scheduleTypingHistoryCommit()

            // Consume the programmatic override first, before it can be
            // confused with the native event's own inputType -- see
            // pendingSourceOverrideRef's declaration.
            const override = pendingSourceOverrideRef.current
            pendingSourceOverrideRef.current = null
            if (override === 'programmatic') return

            const inputType = (e.nativeEvent as InputEvent).inputType
            const isExternalPasteOrDrop =
              inputType === 'insertFromPaste' || inputType === 'insertFromPasteAsQuotation' || inputType === 'insertFromDrop'
            if (isExternalPasteOrDrop) {
              const pasted = pendingPasteWordsRef.current
              pendingPasteWordsRef.current = 0
              // Independent of delta sign -- see onActivity's docstring:
              // pasting over a selection can shrink the document while
              // still bringing in a large pasted block.
              if (pasted > 0) onActivity?.({ typedWords: 0, pastedWords: pasted, deletedWords: 0 })
              return
            }

            const classification = classifyInputType(inputType)
            if (classification === 'other') return
            onTypingInput?.()
            const delta = newCount - prevCount
            // Sign of the delta decides typed vs. deleted -- not which of
            // 'typed'/'delete' classifyInputType returned, per the P0.11
            // spec (a delete-classified edit that somehow nets positive, or
            // vice versa, should still land in the count matching what
            // actually happened to the word count).
            if (delta > 0) {
              onActivity?.({ typedWords: delta, pastedWords: 0, deletedWords: 0 })
            } else if (delta < 0) {
              onActivity?.({ typedWords: 0, pastedWords: 0, deletedWords: -delta })
            }
          }}
          onKeyDown={(e) => {
            // Undo/redo bypasses document.execCommand entirely (see
            // performUndo/performRedo) -- list/checklist operations never
            // participated reliably in native browser history, and a
            // coherent editor can't split typing into one history and
            // structural edits into another. Checked before anything else
            // so it can never fall through to handleEditorKeyDown's own
            // (now-removed) native undo/redo handling.
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
              e.preventDefault()
              if (e.shiftKey) performRedo()
              else performUndo()
              return
            }
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
              e.preventDefault()
              performRedo()
              return
            }
            if (e.key === ' ' && handleMarkdownShortcut(e)) return
            if (handleEditorKeyDown(e, withHistoryCommit)) {
              onChange(serializeEditorHtml(ref.current))
            }
          }}
          onPaste={(e) => {
            const text = e.clipboardData?.getData('text/plain') ?? ''
            pendingPasteWordsRef.current = countPlainTextWords(text)
            // Native paste behavior (and its resulting formatting) is
            // intentionally left alone -- only counting the clipboard's own
            // word count for the classifier above, not intercepting the
            // paste itself.
          }}
          onDragStart={() => {
            internalDragActiveRef.current = true
          }}
          onDragEnd={() => {
            internalDragActiveRef.current = false
          }}
          onDrop={(e) => {
            // A drag that started inside this same editor (reordering a
            // paragraph) must not count as "words pasted" -- only a drop
            // whose content actually came from outside does.
            const text = internalDragActiveRef.current ? '' : (e.dataTransfer?.getData('text/plain') ?? '')
            pendingPasteWordsRef.current = countPlainTextWords(text)
            internalDragActiveRef.current = false
          }}
          onMouseDown={(e) => {
            // Search 2.0: a click anywhere in the editor also ends the
            // temporary jump-to-occurrence highlight, same as typing does.
            clearSearchHighlight()
            const li = (e.target as HTMLElement).closest?.('li.checklist-item') as HTMLLIElement | null
            if (!li || !ref.current?.contains(li)) return
            const rect = li.getBoundingClientRect()
            const emPx = parseFloat(getComputedStyle(li).fontSize) || 16
            const zoneLeft = rect.left - 1.7 * emPx
            const zoneRight = rect.left - 0.3 * emPx
            if (e.clientX >= zoneLeft && e.clientX <= zoneRight) {
              e.preventDefault()
              withHistoryCommit(() => li.classList.toggle('checked'))
              onChange(serializeEditorHtml(ref.current))
            }
          }}
          onClick={(e) => {
            const anchor = (e.target as HTMLElement).closest?.('a') as HTMLAnchorElement | null
            if (!anchor || !ref.current?.contains(anchor) || !internalReferenceIdentity(anchor)) return
            e.preventDefault()
            void resolveInternalReference(anchor).then((resolved) => {
              if (resolved) onNavigateInternalReference(resolved.route)
            })
          }}
          role="textbox"
          aria-multiline="true"
          aria-label="Chapter content"
          data-placeholder="Start writing…"
        />
      </div>
      {linkSelection !== null && (
        <LinkDialog
          selectedText={linkSelection}
          onClose={() => {
            savedLinkRangeRef.current = null
            setLinkSelection(null)
            ref.current?.focus()
          }}
          onExternal={(url) => applyLink(url)}
          onInternal={(target) => applyLink(`calwriter://${target.targetType}/${target.targetId}`, target)}
        />
      )}
    </div>
  )
}
