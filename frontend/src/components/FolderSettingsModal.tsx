import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { FolderDetail } from '../api/types'
import SharingSection from './SharingSection'

export default function FolderSettingsModal({
  folder,
  saving,
  onClose,
  onSave,
  onDelete,
  onLeave,
  canEdit = true,
}: {
  folder: FolderDetail
  saving: boolean
  onClose: () => void
  onSave: (data: { name: string; description: string; showBookColor: boolean }) => void
  onDelete: () => void
  onLeave?: () => void
  canEdit?: boolean
}) {
  const [name, setName] = useState(folder.name)
  const [description, setDescription] = useState(folder.description)
  const [showBookColor, setShowBookColor] = useState(folder.showBookColor)
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
    name.trim() !== folder.name || description !== folder.description || showBookColor !== folder.showBookColor

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
        aria-labelledby="folder-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="folder-modal-title">Folder settings</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="modal-section" onSubmit={handleSubmit}>
          <label htmlFor="folder-modal-name">Name</label>
          <input
            id="folder-modal-name"
            ref={inputRef}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canEdit}
          />
          <label htmlFor="folder-modal-description" style={{ marginTop: '14px' }}>
            Description
          </label>
          <textarea
            id="folder-modal-description"
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
              className="folder-action primary"
              style={{ marginTop: '14px' }}
              disabled={saving || !name.trim() || !changed}
            >
              Save
            </button>
          )}
        </form>

        <div className="modal-section">
          <label>Export</label>
          <div className="modal-export-links">
            <a className="folder-action" href={`/api/folders/${folder.id}/export.docx`}>Export .docx</a>
            <a className="folder-action" href={`/api/folders/${folder.id}/export.rtf`}>Export .rtf</a>
            <a className="folder-action" href={`/api/folders/${folder.id}/export.txt`}>Export .txt</a>
            <a className="folder-action" href={`/api/folders/${folder.id}/export.md`}>Export .md</a>
          </div>
        </div>

        {canEdit && (
          <SharingSection resourceType="folder" resourceId={folder.id} resourceNoun="folder" collapsible />
        )}

        <div className="modal-section chapter-modal-danger">
          {onLeave && (
            <button type="button" className="folder-action danger" onClick={onLeave}>
              Leave folder
            </button>
          )}
          {canEdit && (
            <button type="button" className="folder-action danger" onClick={onDelete}>
              Delete folder
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
