import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useFolder, useChapter, useFolderStats, useChapterStats, useWorkspaceStats } from '../api/hooks'

const DAY_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 0, label: 'All time' },
]

export default function StatsPage() {
  const { folderId, chapterId } = useParams()
  const fId = folderId ? Number(folderId) : undefined
  const cId = chapterId ? Number(chapterId) : undefined
  const isWorkspace = fId === undefined && cId === undefined
  const [days, setDays] = useState(7)
  const folderStats = useFolderStats(fId, days)
  const chapterStats = useChapterStats(cId, days)
  const workspaceStats = useWorkspaceStats(days, isWorkspace)
  const { data: stats, isLoading } = fId !== undefined ? folderStats : cId !== undefined ? chapterStats : workspaceStats
  const backTo = fId !== undefined ? `/folders/${fId}` : cId !== undefined ? `/chapters/${cId}` : '/'

  const { data: folder } = useFolder(fId)
  const { data: chapter } = useChapter(cId)
  const resourceName = fId !== undefined ? folder?.name : cId !== undefined ? chapter?.name : undefined
  const resourceType =
    fId !== undefined ? (folder?.parentId === null ? 'Book' : 'Sub-folder') : cId !== undefined ? 'Chapter' : undefined

  const entries = stats ? Object.entries(stats.wordsPerDay).sort(([a], [b]) => a.localeCompare(b)) : []
  const maxCount = Math.max(1, ...entries.map(([, count]) => count))

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to={backTo}>&larr; {isWorkspace ? 'Books' : 'Back'}</Link>
          </div>
          <h1>{isWorkspace ? 'Workspace Stats' : `${resourceName ?? '…'} Stats`}</h1>
          {resourceType && <p className="folder-author">{resourceType}</p>}
        </div>
      </header>

      <section className="folder-section stats-section">
        <div className="stats-summary-tile">
          <span className="stats-summary-value">
            {isLoading ? '—' : (stats?.totalWords ?? 0).toLocaleString()}
          </span>
          <span className="stats-summary-label">Total words</span>
        </div>

        <div className="folder-section-header">
          <div>
            <h2>Words per day</h2>
            <p>Word count as of each day's last edit.</p>
          </div>
          <label className="stats-days-select">
            <span>Show</span>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {DAY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {isLoading && <p className="folder-empty-state">Loading…</p>}
        {!isLoading && entries.length === 0 && <p className="folder-empty-state">No activity yet.</p>}
        {!isLoading && entries.length > 0 && (
          <div className="stats-chart">
            {entries.map(([day, count]) => (
              <div key={day} className="stats-bar-column">
                <span className="stats-bar-count">{count}</span>
                <div
                  className="stats-bar"
                  style={{ height: `${Math.max(4, (count / maxCount) * 100)}%` }}
                  title={`${count.toLocaleString()} words`}
                />
                <span className="stats-bar-day">{day.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
