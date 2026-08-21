import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useSidebarVisibility } from '../context/SidebarVisibilityContext'
import { useShortcutsModal } from '../context/ShortcutsModalContext'

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

function handleEditorKeyDown(e: KeyboardEvent<HTMLDivElement>) {
  if (e.key === 'Tab') {
    e.preventDefault()
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
}: {
  chapterId: number
  initialHtml: string
  onChange: (html: string) => void
  onWordCountChange?: (count: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const characterPickerRef = useRef<HTMLDivElement>(null)
  const lastLoadedChapterId = useRef<number | null>(null)
  const [showCharacters, setShowCharacters] = useState(false)
  const { sidebarHidden, toggleSidebar } = useSidebarVisibility()
  const { open: openShortcuts } = useShortcutsModal()
  const [isFullWidth, setIsFullWidth] = useState(() => {
    try {
      return localStorage.getItem(FULL_WIDTH_KEY) === 'true'
    } catch {
      return false
    }
  })

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

  return (
    <div className={`chapter-editor-shell${isFullWidth ? ' full-width' : ''}`}>
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
        <span className="toolbar-spacer" />
        <button
          type="button"
          className="editor-width-toggle"
          onClick={toggleSidebar}
          aria-pressed={sidebarHidden}
          title={sidebarHidden ? 'Show sidebar' : 'Hide sidebar'}
        >
          {sidebarHidden ? 'Show sidebar' : 'Hide sidebar'}
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
            onChange(ref.current?.innerHTML ?? '')
            onWordCountChange?.(countWords(ref.current))
          }}
          onKeyDown={(e) => {
            if (handleEditorKeyDown(e)) {
              onChange(ref.current?.innerHTML ?? '')
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
