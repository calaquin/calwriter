import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChapterDetail } from '../api/types'

export default function ChapterSettingsModal({
  chapter,
  saving,
  onClose,
  onSave,
  onDelete,
}: {
  chapter: ChapterDetail
  saving: boolean
  onClose: () => void
  onSave: (data: { name: string; description: string }) => void
  onDelete: () => void
}) {
  const [name, setName] = useState(chapter.name)
  const [description, setDescription] = useState(chapter.description)
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

  const changed = name.trim() !== chapter.name || description !== chapter.description

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || !changed) return
    onSave({ name: trimmed, description })
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chapter-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="chapter-modal-title">Chapter settings</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="modal-section" onSubmit={handleSubmit}>
          <label htmlFor="chapter-modal-name">Name</label>
          <input
            id="chapter-modal-name"
            ref={inputRef}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <label htmlFor="chapter-modal-description" style={{ marginTop: '14px' }}>
            Description
          </label>
          <textarea
            id="chapter-modal-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
          <button
            type="submit"
            className="chapter-action primary"
            style={{ marginTop: '14px' }}
            disabled={saving || !name.trim() || !changed}
          >
            Save
          </button>
        </form>

        <div className="modal-section">
          <a className="chapter-action" href={`/api/chapters/${chapter.id}/export.docx`}>
            Export .docx
          </a>
        </div>

        <div className="modal-section chapter-modal-danger">
          <button type="button" className="chapter-action danger" onClick={onDelete}>
            Delete chapter
          </button>
        </div>
      </div>
    </div>
  )
}
