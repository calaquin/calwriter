import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { useShortcutsModal } from '../context/ShortcutsModalContext'
import { copyText } from '../utils/clipboard'

const FULL_WIDTH_KEY = 'calwriter:editorFullWidth'

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

function execCmd(command: string, value?: string) {
  document.execCommand(command, false, value)
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

function clearBlockText(block: HTMLElement) {
  const selection = window.getSelection()
  if (!selection) return
  const range = document.createRange()
  range.selectNodeContents(block)
  selection.removeAllRanges()
  selection.addRange(range)
  document.execCommand('delete')
}

function handleEditorKeyDown(e: KeyboardEvent<HTMLDivElement>) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const li = closestListItem(e.currentTarget)
    if (li) {
      return e.shiftKey ? outdentListItem(li) : indentListItem(li)
    }
    return setFirstLineIndent(e.currentTarget, e.shiftKey)
  }
  if (e.key === 'Backspace' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const editor = e.currentTarget
    const anchor = window.getSelection()?.anchorNode
    const anchorEl = anchor instanceof HTMLElement ? anchor : anchor?.parentElement
    const block = anchorEl?.closest<HTMLElement>('p, div')
    if (block && block !== editor && editor.contains(block) && (parseFloat(block.style.textIndent) || 0) > 0) {
      if (isCaretAtStartOfBlock(block)) {
        e.preventDefault()
        return setFirstLineIndent(editor, true)
      }
    }
  }
  // Chrome applies bold/italic/underline/undo/redo for these combos natively
  // on any contenteditable, but Firefox reserves Ctrl+B (bookmarks sidebar)
  // and Ctrl+U (view source) as browser-chrome shortcuts and never hands them
  // to the page -- so they have to be handled explicitly and preventDefault'd
  // here to work consistently across browsers.
  if (!e.ctrlKey && !e.metaKey) return
  switch (e.key.toLowerCase()) {
    case 'b':
      e.preventDefault()
      execCmd('bold')
      return false
    case 'i':
      e.preventDefault()
      execCmd('italic')
      return false
    case 'u':
      e.preventDefault()
      execCmd('underline')
      return false
    case 'z':
      e.preventDefault()
      execCmd(e.shiftKey ? 'redo' : 'undo')
      return false
    case 'y':
      e.preventDefault()
      execCmd('redo')
      return false
  }
  return false
}

export default function ChapterEditor({
  chapterId,
  initialHtml,
  onChange,
  onWordCountChange,
  bookColor,
  writeMode,
  onToggleWriteMode,
  completed,
  onToggleComplete,
}: {
  chapterId: string
  initialHtml: string
  onChange: (html: string) => void
  onWordCountChange?: (count: number) => void
  /** Resolved book color to tint the editor background with, or null/undefined
   * to leave the editor at its plain theme background. */
  bookColor?: string | null
  /** Distraction-free mode: hides the app sidebar plus everything above this
   * toolbar (chapter tabs, header) -- driven by the parent ChapterPage since
   * that's what owns the tabs/header being hidden. */
  writeMode: boolean
  onToggleWriteMode: () => void
  /** Chapter's own completed_at !== null -- surfaced here too (also settable
   * from Chapter Settings and the Book/Sub-Folder chapter list) so marking a
   * chapter done doesn't require leaving the editor. Optional since not
   * every caller of this component (there is only one today, ChapterPage)
   * necessarily has permission to toggle it. */
  completed?: boolean
  onToggleComplete?: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const characterPickerRef = useRef<HTMLDivElement>(null)
  const lastLoadedChapterId = useRef<string | null>(null)
  const [showCharacters, setShowCharacters] = useState(false)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const { open: openShortcuts } = useShortcutsModal()
  const [isFullWidth, setIsFullWidth] = useState(() => {
    try {
      return localStorage.getItem(FULL_WIDTH_KEY) === 'true'
    } catch {
      return false
    }
  })

  async function copyAllText() {
    const text = ref.current?.innerText ?? ''
    setCopyStatus((await copyText(text)) ? 'copied' : 'error')
    setTimeout(() => setCopyStatus('idle'), 2000)
  }

  // Only set innerHTML when we switch chapters, never on every render --
  // otherwise React would clobber the cursor position on each keystroke.
  useEffect(() => {
    if (ref.current && lastLoadedChapterId.current !== chapterId) {
      ref.current.innerHTML = initialHtml
      lastLoadedChapterId.current = chapterId
      onWordCountChange?.(countWords(ref.current))
    }
  }, [chapterId, initialHtml, onWordCountChange])

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
    execCmd(command, value)
    ref.current?.focus()
    onChange(ref.current?.innerHTML ?? '')
    onWordCountChange?.(countWords(ref.current))
  }

  function runParagraphIndent(remove: boolean) {
    if (ref.current && setFirstLineIndent(ref.current, remove)) {
      onChange(ref.current.innerHTML)
    }
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
    if (!closestListItem(editor)) execCmd('insertUnorderedList')
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
    onChange(editor.innerHTML)
    onWordCountChange?.(countWords(editor))
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
      clearBlockText(block)
      execCmd('insertUnorderedList')
      onChange(editor.innerHTML)
      onWordCountChange?.(countWords(editor))
      return true
    }
    if (/^\d+\.$/.test(text)) {
      e.preventDefault()
      clearBlockText(block)
      execCmd('insertOrderedList')
      onChange(editor.innerHTML)
      onWordCountChange?.(countWords(editor))
      return true
    }
    if (/^\[ ?\]$/.test(text)) {
      e.preventDefault()
      clearBlockText(block)
      applyChecklist(false)
      return true
    }
    if (/^\[[xX]\]$/.test(text)) {
      e.preventDefault()
      clearBlockText(block)
      applyChecklist(true)
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
        <button type="button" className="icon-btn icon-undo" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('undo')} title="Undo (Ctrl+Z)" aria-label="Undo" />
        <button type="button" className="icon-btn icon-redo" onMouseDown={(e) => e.preventDefault()} onClick={() => runCommand('redo')} title="Redo (Ctrl+Y)" aria-label="Redo" />
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
          onInput={() => {
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
            onChange(editor?.innerHTML ?? '')
            onWordCountChange?.(countWords(editor))
          }}
          onKeyDown={(e) => {
            if (e.key === ' ' && handleMarkdownShortcut(e)) return
            if (handleEditorKeyDown(e)) {
              onChange(ref.current?.innerHTML ?? '')
            }
          }}
          onMouseDown={(e) => {
            const li = (e.target as HTMLElement).closest?.('li.checklist-item') as HTMLLIElement | null
            if (!li || !ref.current?.contains(li)) return
            const rect = li.getBoundingClientRect()
            const emPx = parseFloat(getComputedStyle(li).fontSize) || 16
            const zoneLeft = rect.left - 1.7 * emPx
            const zoneRight = rect.left - 0.3 * emPx
            if (e.clientX >= zoneLeft && e.clientX <= zoneRight) {
              e.preventDefault()
              li.classList.toggle('checked')
              onChange(ref.current.innerHTML)
            }
          }}
          role="textbox"
          aria-multiline="true"
          aria-label="Chapter content"
          data-placeholder="Start writing…"
        />
      </div>
    </div>
  )
}
