import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useChapterVersions, useChapterVersion, useRestoreChapterVersion } from '../api/hooks'
import ConfirmModal from './ConfirmModal'
import VersionDiffView from './VersionDiffView'
import { type Selection, sameSelection, selectionKey, formatVersionTimestamp } from '../utils/versionSelection'

export default function ChapterHistoryModal({
  chapterId,
  currentContentHtml,
  currentWordCount,
  onClose,
  onRestored,
}: {
  chapterId: string
  currentContentHtml: string
  currentWordCount: number
  onClose: () => void
  onRestored: () => void
}) {
  const { data: versions, isLoading } = useChapterVersions(chapterId, true)
  const [selected, setSelected] = useState<Selection>({ kind: 'current' })
  const [compare, setCompare] = useState<Selection>(null)
  const { data: selectedVersion } = useChapterVersion(chapterId, selected?.kind === 'version' ? selected.id : undefined)
  const { data: compareVersion } = useChapterVersion(chapterId, compare?.kind === 'version' ? compare.id : undefined)
  const restore = useRestoreChapterVersion(chapterId)
  const [confirmingRestore, setConfirmingRestore] = useState(false)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function selectPrimary(next: Selection) {
    setSelected(next)
    // Can't diff a version against itself -- drop the comparison rather
    // than silently showing a diff with nothing in it.
    if (sameSelection(next, compare)) setCompare(null)
  }

  function handleRestore() {
    if (selected?.kind !== 'version') return
    setConfirmingRestore(true)
  }

  function confirmRestore() {
    if (selected?.kind !== 'version') return
    restore.mutate(selected.id, {
      onSuccess: () => {
        onRestored()
        onClose()
      },
    })
  }

  const previewHtml = selected?.kind === 'current' ? currentContentHtml : selectedVersion?.contentHtml
  const compareHtml = compare?.kind === 'current' ? currentContentHtml : compareVersion?.contentHtml
  const diffReady = compare !== null && previewHtml !== undefined && compareHtml !== undefined

  // "Compare with" options: every version plus Current, minus whichever one
  // is already the primary selection (see selectPrimary's same-selection guard).
  const compareOptions: { key: string; sel: Selection; label: string }[] = []
  if (selected?.kind !== 'current') {
    compareOptions.push({ key: 'current', sel: { kind: 'current' }, label: 'Current' })
  }
  for (const v of versions ?? []) {
    if (selected?.kind === 'version' && selected.id === v.id) continue
    compareOptions.push({ key: v.id, sel: { kind: 'version', id: v.id }, label: formatVersionTimestamp(v.createdAt) })
  }

  function handleCompareChange(key: string) {
    if (key === 'none') {
      setCompare(null)
      return
    }
    const option = compareOptions.find((o) => o.key === key)
    setCompare(option ? option.sel : null)
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className={`modal-dialog history-modal${compare !== null ? ' comparing' : ''}`}
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
              className={`history-version-item${selected?.kind === 'current' ? ' active' : ''}`}
              onClick={() => selectPrimary({ kind: 'current' })}
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
                className={`history-version-item${selected?.kind === 'version' && selected.id === v.id ? ' active' : ''}`}
                onClick={() => selectPrimary({ kind: 'version', id: v.id })}
              >
                <span className="history-version-time">{formatVersionTimestamp(v.createdAt)}</span>
                <span className="history-version-meta">{v.wordCount.toLocaleString()} words</span>
                <span className="history-version-preview">{v.preview || '(empty)'}</span>
              </button>
            ))}
          </div>
          <div className="history-version-preview-pane">
            {previewHtml !== undefined ? (
              <>
                <div className="history-compare-row">
                  <label className="history-compare-label">
                    <span>Compare with</span>
                    <select value={selectionKey(compare)} onChange={(e) => handleCompareChange(e.target.value)}>
                      <option value="none">— None (show one version) —</option>
                      {compareOptions.map((o) => (
                        <option key={o.key} value={o.key}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {compare !== null && (
                    <Link
                      className="history-full-page-link"
                      to={`/chapters/${chapterId}/diff?from=${selectionKey(selected)}&to=${selectionKey(compare)}`}
                      title="Open this comparison in its own page"
                    >
                      Open full page ↗
                    </Link>
                  )}
                </div>
                {compare === null ? (
                  <div className="history-preview-content" dangerouslySetInnerHTML={{ __html: previewHtml }} />
                ) : diffReady ? (
                  <VersionDiffView
                    fromLabel={selected?.kind === 'current' ? 'Current' : formatVersionTimestamp(selectedVersion!.createdAt)}
                    toLabel={compare.kind === 'current' ? 'Current' : formatVersionTimestamp(compareVersion!.createdAt)}
                    fromHtml={previewHtml}
                    toHtml={compareHtml!}
                  />
                ) : (
                  <p className="history-empty">Loading…</p>
                )}
                {selected?.kind === 'version' && (
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
