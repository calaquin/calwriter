import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useChapter, useChapterVersions, useChapterVersion, useRestoreChapterVersion } from '../api/hooks'
import VersionDiffView from '../components/VersionDiffView'
import ConfirmModal from '../components/ConfirmModal'
import { type Selection, parseSelectionKey, selectionKey, formatVersionTimestamp } from '../utils/versionSelection'

export default function ChapterDiffPage() {
  const { chapterId } = useParams()
  const id = chapterId
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { data: chapter, isLoading: chapterLoading, error } = useChapter(id)
  const { data: versions, isLoading: versionsLoading } = useChapterVersions(id, true)
  const restore = useRestoreChapterVersion(id ?? '')
  const [confirmingRestore, setConfirmingRestore] = useState<Selection>(null)

  const from = parseSelectionKey(searchParams.get('from'))
  const to = parseSelectionKey(searchParams.get('to'))

  // Default to "most recent checkpoint vs. Current" the first time this page
  // loads without explicit ?from=/&to= (e.g. navigated to directly, not via
  // the history modal's "Open full page" link).
  useEffect(() => {
    if (!versions || searchParams.has('from') || searchParams.has('to')) return
    const next = new URLSearchParams(searchParams)
    next.set('from', versions[0] ? versions[0].id : 'current')
    next.set('to', 'current')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versions])

  const { data: fromVersion } = useChapterVersion(id, from?.kind === 'version' ? from.id : undefined)
  const { data: toVersion } = useChapterVersion(id, to?.kind === 'version' ? to.id : undefined)

  if (chapterLoading || versionsLoading) return <p>Loading...</p>
  if (error || !chapter) return <p>Not found, or you don't have access to it.</p>

  const options: { key: string; sel: Selection; label: string }[] = [
    { key: 'current', sel: { kind: 'current' }, label: 'Current' },
    ...(versions ?? []).map((v) => ({
      key: v.id,
      sel: { kind: 'version' as const, id: v.id },
      label: formatVersionTimestamp(v.createdAt),
    })),
  ]

  function handleFromChange(key: string) {
    const next = new URLSearchParams(searchParams)
    next.set('from', key)
    setSearchParams(next, { replace: true })
  }

  function handleToChange(key: string) {
    const next = new URLSearchParams(searchParams)
    next.set('to', key)
    setSearchParams(next, { replace: true })
  }

  const fromHtml = from?.kind === 'current' ? chapter.contentHtml : fromVersion?.contentHtml
  const toHtml = to?.kind === 'current' ? chapter.contentHtml : toVersion?.contentHtml
  const fromLabel = from?.kind === 'current' ? 'Current' : fromVersion ? formatVersionTimestamp(fromVersion.createdAt) : '…'
  const toLabel = to?.kind === 'current' ? 'Current' : toVersion ? formatVersionTimestamp(toVersion.createdAt) : '…'

  function confirmRestore() {
    if (confirmingRestore?.kind !== 'version') return
    restore.mutate(confirmingRestore.id, {
      onSuccess: () => {
        setConfirmingRestore(null)
        navigate(`/chapters/${id}`)
      },
    })
  }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to={`/chapters/${id}`}>&larr; {chapter.name}</Link>
          </div>
          <h1>Version Diff</h1>
        </div>
      </header>

      <section className="folder-section diff-page-section">
        <div className="diff-page-selectors">
          <label className="history-compare-label">
            <span>From</span>
            <select value={selectionKey(from)} onChange={(e) => handleFromChange(e.target.value)}>
              {options.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="history-compare-label">
            <span>To</span>
            <select value={selectionKey(to)} onChange={(e) => handleToChange(e.target.value)}>
              {options.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {fromHtml !== undefined && toHtml !== undefined ? (
          <>
            <VersionDiffView fromLabel={fromLabel} toLabel={toLabel} fromHtml={fromHtml} toHtml={toHtml} />
            {(from?.kind === 'version' || to?.kind === 'version') && (
              <div className="diff-page-restore-row">
                {from?.kind === 'version' && (
                  <button type="button" className="chapter-action" onClick={() => setConfirmingRestore(from)}>
                    Restore "{fromLabel}"
                  </button>
                )}
                {to?.kind === 'version' && (
                  <button type="button" className="chapter-action" onClick={() => setConfirmingRestore(to)}>
                    Restore "{toLabel}"
                  </button>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="folder-empty-state">Loading…</p>
        )}
      </section>

      {confirmingRestore && (
        <ConfirmModal
          title="Restore version"
          message="Restore this version? Your current content will be saved as a checkpoint first, so this can be undone too."
          confirmLabel="Restore"
          danger={false}
          pending={restore.isPending}
          onConfirm={confirmRestore}
          onCancel={() => setConfirmingRestore(null)}
        />
      )}
    </div>
  )
}
