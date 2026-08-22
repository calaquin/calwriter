import { useEffect, useRef, useState, type FormEvent } from 'react'

export default function RenameModal({
  title,
  initialValue,
  saving = false,
  onClose,
  onSave,
}: {
  title: string
  initialValue: string
  saving?: boolean
  onClose: () => void
  onSave: (name: string) => void
}) {
  const [name, setName] = useState(initialValue)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const trimmed = name.trim()
  const changed = trimmed !== initialValue

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!trimmed || !changed) return
    onSave(trimmed)
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rename-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="rename-modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="modal-section" onSubmit={handleSubmit}>
          <label htmlFor="rename-modal-name">Name</label>
          <input
            id="rename-modal-name"
            ref={inputRef}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            type="submit"
            className="folder-action primary"
            style={{ marginTop: '14px' }}
            disabled={saving || !trimmed || !changed}
          >
            Save
          </button>
        </form>
      </div>
    </div>
  )
}
