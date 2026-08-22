import { useEffect } from 'react'

export default function ConfirmModal({
  title,
  message,
  confirmLabel = 'Confirm',
  danger = true,
  pending = false,
  onConfirm,
  onCancel,
}: {
  title: string
  message: string
  confirmLabel?: string
  /** Styles the confirm button as destructive. Defaults to true since most
   * confirmations in this app guard a destructive or hard-to-undo action. */
  danger?: boolean
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onCancel])

  return (
    <div className="modal-overlay" role="presentation" onClick={onCancel}>
      <div
        className="modal-dialog confirm-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="confirm-modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onCancel} aria-label="Close">
            ×
          </button>
        </div>

        <div className="modal-section">
          <p className="confirm-modal-message">{message}</p>
          <div className="settings-form-actions">
            <button type="button" className="settings-secondary-action" onClick={onCancel} autoFocus>
              Cancel
            </button>
            <button
              type="button"
              className={`settings-primary-action${danger ? ' danger' : ''}`}
              onClick={onConfirm}
              disabled={pending}
            >
              {pending ? 'Working…' : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
