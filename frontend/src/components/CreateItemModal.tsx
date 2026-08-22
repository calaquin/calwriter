import { useEffect, useRef, useState, type FormEvent } from 'react'

export default function CreateItemModal({
  title,
  nameLabel,
  saving,
  onClose,
  onCreate,
}: {
  title: string
  nameLabel: string
  saving: boolean
  onClose: () => void
  onCreate: (data: { name: string; description: string }) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    onCreate({ name: trimmed, description })
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-item-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="create-item-modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="modal-section" onSubmit={handleSubmit}>
          <label htmlFor="create-item-modal-name">{nameLabel}</label>
          <input
            id="create-item-modal-name"
            ref={inputRef}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <label htmlFor="create-item-modal-description" style={{ marginTop: '14px' }}>
            Description
          </label>
          <textarea
            id="create-item-modal-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
          <button
            type="submit"
            className="folder-action primary"
            style={{ marginTop: '14px' }}
            disabled={saving || !name.trim()}
          >
            Create
          </button>
        </form>
      </div>
    </div>
  )
}
