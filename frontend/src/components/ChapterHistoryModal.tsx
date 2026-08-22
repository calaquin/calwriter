import { useEffect, useState } from 'react'
import { useChapterVersions, useChapterVersion, useRestoreChapterVersion } from '../api/hooks'
import ConfirmModal from './ConfirmModal'

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

type Selection = number | 'current' | null

export default function ChapterHistoryModal({
  chapterId,
  currentContentHtml,
  currentWordCount,
  onClose,
  onRestored,
}: {
  chapterId: number
  currentContentHtml: string
  currentWordCount: number
  onClose: () => void
  onRestored: () => void
}) {
  const { data: versions, isLoading } = useChapterVersions(chapterId, true)
  const [selected, setSelected] = useState<Selection>('current')
  const { data: selectedVersion } = useChapterVersion(chapterId, typeof selected === 'number' ? selected : undefined)
  const restore = useRestoreChapterVersion(chapterId)
  const [confirmingRestore, setConfirmingRestore] = useState(false)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function handleRestore() {
    if (typeof selected !== 'number') return
    setConfirmingRestore(true)
  }

  function confirmRestore() {
    if (typeof selected !== 'number') return
    restore.mutate(selected, {
      onSuccess: () => {
        onRestored()
        onClose()
      },
    })
  }

  const previewHtml = selected === 'current' ? currentContentHtml : selectedVersion?.contentHtml

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog history-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="history-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="history-modal-title">Version history</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="history-modal-body">
          <div className="history-version-list">
            <button
              type="button"
              className={`history-version-item${selected === 'current' ? ' active' : ''}`}
              onClick={() => setSelected('current')}
            >
              <span className="history-version-time">Current</span>
              <span className="history-version-meta">{currentWordCount.toLocaleString()} words</span>
              <span className="history-version-preview">What's in the editor right now</span>
            </button>
            {isLoading && <p className="history-empty">Loading…</p>}
            {!isLoading && versions?.length === 0 && (
              <p className="history-empty">No earlier checkpoints yet. They're created automatically as you edit.</p>
            )}
            {versions?.map((v) => (
              <button
                key={v.id}
                type="button"
                className={`history-version-item${v.id === selected ? ' active' : ''}`}
                onClick={() => setSelected(v.id)}
              >
                <span className="history-version-time">{formatTimestamp(v.createdAt)}</span>
                <span className="history-version-meta">{v.wordCount.toLocaleString()} words</span>
                <span className="history-version-preview">{v.preview || '(empty)'}</span>
              </button>
            ))}
          </div>
          <div className="history-version-preview-pane">
            {previewHtml !== undefined ? (
              <>
                <div className="history-preview-content" dangerouslySetInnerHTML={{ __html: previewHtml }} />
                {typeof selected === 'number' && (
                  <button
                    type="button"
                    className="chapter-action primary"
                    onClick={handleRestore}
                    disabled={restore.isPending}
                  >
                    {restore.isPending ? 'Restoring…' : 'Restore this version'}
                  </button>
                )}
              </>
            ) : (
              <p className="history-empty">Loading…</p>
            )}
          </div>
        </div>
      </div>
      {confirmingRestore && (
        <ConfirmModal
          title="Restore version"
          message="Restore this version? Your current content will be saved as a checkpoint first, so this can be undone too."
          confirmLabel="Restore"
          danger={false}
          pending={restore.isPending}
          onConfirm={confirmRestore}
          onCancel={() => setConfirmingRestore(false)}
        />
      )}
    </div>
  )
}
