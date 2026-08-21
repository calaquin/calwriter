import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { FolderDetail } from '../api/types'

export default function FolderSettingsModal({
  folder,
  saving,
  onClose,
  onSave,
}: {
  folder: FolderDetail
  saving: boolean
  onClose: () => void
  onSave: (data: { name: string; description: string }) => void
}) {
  const [name, setName] = useState(folder.name)
  const [description, setDescription] = useState(folder.description)
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

  const changed = name.trim() !== folder.name || description !== folder.description

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
        aria-labelledby="folder-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="folder-modal-title">Sub-folder settings</h2>
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
          />
          <label htmlFor="folder-modal-description" style={{ marginTop: '14px' }}>
            Description
          </label>
          <textarea
            id="folder-modal-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
          <button
            type="submit"
            className="folder-action primary"
            style={{ marginTop: '14px' }}
            disabled={saving || !name.trim() || !changed}
          >
            Save
          </button>
        </form>
      </div>
    </div>
  )
}
