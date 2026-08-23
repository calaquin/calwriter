import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChapterDetail } from '../api/types'
import SharingSection from './SharingSection'

export default function ChapterSettingsModal({
  chapter,
  saving,
  onClose,
  onSave,
  onDelete,
  onLeave,
  onToggleComplete,
  canEdit = true,
}: {
  chapter: ChapterDetail
  saving: boolean
  onClose: () => void
  onSave: (data: { name: string; description: string; showBookColor: boolean }) => void
  onDelete: () => void
  onLeave?: () => void
  onToggleComplete?: (completed: boolean) => void
  canEdit?: boolean
}) {
  const [name, setName] = useState(chapter.name)
  const [description, setDescription] = useState(chapter.description)
  const [showBookColor, setShowBookColor] = useState(chapter.showBookColor)
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

  const changed =
    name.trim() !== chapter.name || description !== chapter.description || showBookColor !== chapter.showBookColor

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || !changed) return
    onSave({ name: trimmed, description, showBookColor })
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog wizard-modal"
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
            disabled={!canEdit}
          />
          <label htmlFor="chapter-modal-description" style={{ marginTop: '14px' }}>
            Description
          </label>
          <textarea
            id="chapter-modal-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            disabled={!canEdit}
          />
          <label className="chapter-complete-toggle" style={{ marginTop: '14px' }}>
            <input
              type="checkbox"
              checked={showBookColor}
              onChange={(e) => setShowBookColor(e.target.checked)}
              disabled={!canEdit}
            />
            Use book color as a subtle editor background
          </label>
          {canEdit && (
            <button
              type="submit"
              className="chapter-action primary"
              style={{ marginTop: '14px' }}
              disabled={saving || !name.trim() || !changed}
            >
              Save
            </button>
          )}
        </form>

        {onToggleComplete && (
          <div className="modal-section">
            <label className="chapter-complete-toggle">
              <input
                type="checkbox"
                checked={chapter.completedAt !== null}
                onChange={(e) => onToggleComplete(e.target.checked)}
                disabled={!canEdit}
              />
              Complete
            </label>
          </div>
        )}

        <div className="modal-section">
          <label>Export</label>
          <div className="modal-export-links">
            <a className="chapter-action" href={`/api/chapters/${chapter.id}/export.docx`}>Export .docx</a>
            <a className="chapter-action" href={`/api/chapters/${chapter.id}/export.rtf`}>Export .rtf</a>
            <a className="chapter-action" href={`/api/chapters/${chapter.id}/export.txt`}>Export .txt</a>
            <a className="chapter-action" href={`/api/chapters/${chapter.id}/export.md`}>Export .md</a>
          </div>
        </div>

        {canEdit && (
          <SharingSection resourceType="chapter" resourceId={chapter.id} resourceNoun="chapter" collapsible />
        )}

        <div className="modal-section chapter-modal-danger">
          {onLeave && (
            <button type="button" className="chapter-action danger" onClick={onLeave}>
              Leave chapter
            </button>
          )}
          {canEdit && (
            <button type="button" className="chapter-action danger" onClick={onDelete}>
              Delete chapter
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
