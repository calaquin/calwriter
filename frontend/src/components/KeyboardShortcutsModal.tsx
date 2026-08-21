import { useEffect } from 'react'

const SHORTCUT_GROUPS: { title: string; items: [string, string][] }[] = [
  {
    title: 'Formatting',
    items: [
      ['Ctrl/Cmd + B', 'Bold'],
      ['Ctrl/Cmd + I', 'Italic'],
      ['Ctrl/Cmd + U', 'Underline'],
    ],
  },
  {
    title: 'Editing',
    items: [
      ['Ctrl/Cmd + Z', 'Undo'],
      ['Ctrl/Cmd + Shift + Z, or Ctrl + Y', 'Redo'],
      ['Tab', 'Indent the current line a little more'],
      ['Shift + Tab', 'Outdent the current line'],
      ['Backspace at the start of an indented line', 'Outdent instead of deleting'],
    ],
  },
  {
    title: 'General',
    items: [
      ['Ctrl/Cmd + /', 'Show this shortcuts reference'],
      ['Escape', 'Close the open dialog'],
    ],
  },
]

export default function KeyboardShortcutsModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog shortcuts-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="shortcuts-modal-title">Keyboard shortcuts</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {SHORTCUT_GROUPS.map((group) => (
          <div className="modal-section" key={group.title}>
            <h3 className="shortcuts-group-title">{group.title}</h3>
            <dl className="shortcuts-list">
              {group.items.map(([keys, label]) => (
                <div className="shortcuts-row" key={keys}>
                  <dt>
                    <kbd>{keys}</kbd>
                  </dt>
                  <dd>{label}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}
