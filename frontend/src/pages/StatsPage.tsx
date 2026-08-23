import { useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useFolder,
  useChapter,
  useFolderStats,
  useChapterStats,
  useWorkspaceStats,
  useToggleChapterComplete,
} from '../api/hooks'
import type { HeatmapBucket } from '../api/types'

const DAY_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 0, label: 'All time' },
]

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function formatDuration(totalSeconds: number): string {
  const minutes = Math.round(totalSeconds / 60)
  if (minutes < 1) return '<1m'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `${value}%`
}

function formatSignedPercent(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value}%`
}

/** Day-of-week x hour-of-day activity grid. A single-hue (the app's own ink
 * color) sequential ramp by magnitude, matching the app's monochrome theme
 * (it has no separate brand/accent hue to draw from -- see the "primary"
 * button, which is just inverted --text-color). */
function WritingHeatmap({ buckets }: { buckets: HeatmapBucket[] }) {
  if (buckets.length === 0) {
    return <p className="folder-empty-state">Not enough activity yet to show a heatmap.</p>
  }
  const byCell = new Map<string, number>()
  let max = 0
  for (const b of buckets) {
    byCell.set(`${b.dayOfWeek}-${b.hour}`, b.activeSeconds)
    if (b.activeSeconds > max) max = b.activeSeconds
  }
  return (
    <div className="writing-heatmap">
      <div className="writing-heatmap-grid" role="img" aria-label="Writing activity by day of week and hour of day">
        {DAY_LABELS.map((label, day) => (
          <div className="writing-heatmap-row" key={label}>
            <span className="writing-heatmap-row-label">{label}</span>
            <div className="writing-heatmap-cells">
              {Array.from({ length: 24 }, (_, hour) => {
                const seconds = byCell.get(`${day}-${hour}`) ?? 0
                const intensity = max > 0 ? seconds / max : 0
                return (
                  <span
                    key={hour}
                    className="writing-heatmap-cell"
                    style={{ '--heat': intensity } as CSSProperties}
                    title={`${label} ${hour}:00–${(hour + 1) % 24}:00 — ${
                      seconds > 0 ? formatDuration(seconds) : 'no activity'
                    }`}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="writing-heatmap-legend">
        <span>Less</span>
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <span key={v} className="writing-heatmap-cell" style={{ '--heat': v } as CSSProperties} />
        ))}
        <span>More</span>
      </div>
    </div>
  )
}

export default function StatsPage() {
  const { folderId, chapterId } = useParams()
  const fId = folderId
  const cId = chapterId
  const isWorkspace = fId === undefined && cId === undefined
  const [days, setDays] = useState(7)
  const folderStatsQuery = useFolderStats(fId, days)
  const chapterStatsQuery = useChapterStats(cId, days)
  const workspaceStatsQuery = useWorkspaceStats(days, isWorkspace)
  const { data: stats, isLoading } =
    fId !== undefined ? folderStatsQuery : cId !== undefined ? chapterStatsQuery : workspaceStatsQuery
  const backTo = fId !== undefined ? `/folders/${fId}` : cId !== undefined ? `/chapters/${cId}` : '/'

  const { data: folder } = useFolder(fId)
  const { data: chapter } = useChapter(cId)
  const resourceName = fId !== undefined ? folder?.name : cId !== undefined ? chapter?.name : undefined
  const resourceType =
    fId !== undefined ? (folder?.parentId === null ? 'Book' : 'Sub-folder') : cId !== undefined ? 'Chapter' : undefined

  const toggleComplete = useToggleChapterComplete()

  const entries = stats ? Object.entries(stats.wordsPerDay).sort(([a], [b]) => a.localeCompare(b)) : []
  const maxCount = Math.max(1, ...entries.map(([, count]) => count))

  const workspace = isWorkspace ? workspaceStatsQuery.data : undefined
  const folderExtra = fId !== undefined ? folderStatsQuery.data : undefined
  const chapterExtra = cId !== undefined ? chapterStatsQuery.data : undefined

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
        <div className="stats-tile-row">
          <div className="stats-summary-tile">
            <span className="stats-summary-value">
              {isLoading ? '—' : (stats?.totalWords ?? 0).toLocaleString()}
            </span>
            <span className="stats-summary-label">Total words</span>
          </div>
          {chapterExtra && (
            <div className="stats-summary-tile">
              <span className="stats-summary-value">{chapterExtra.wpm}</span>
              <span className="stats-summary-label">Words / minute (active)</span>
            </div>
          )}
          {workspace && (
            <>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{workspace.streak.current}</span>
                <span className="stats-summary-label">
                  Day streak{workspace.streak.longest > workspace.streak.current ? ` (best ${workspace.streak.longest})` : ''}
                </span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{workspace.avgWpm}</span>
                <span className="stats-summary-label">Words / minute (active)</span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{formatDuration(workspace.totalActiveSeconds)}</span>
                <span className="stats-summary-label">Active writing time</span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{formatPercent(workspace.goalHitRate.percent)}</span>
                <span className="stats-summary-label">
                  Goal hit rate
                  {workspace.goalHitRate.total > 0 ? ` (${workspace.goalHitRate.achieved}/${workspace.goalHitRate.total})` : ''}
                </span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">
                  {workspace.weekOverWeekWords.thisWeek.toLocaleString()}
                </span>
                <span className="stats-summary-label">
                  Words this week ({formatSignedPercent(workspace.weekOverWeekWords.percentChange)} vs last week)
                </span>
              </div>
            </>
          )}
        </div>

        {workspace?.busiestResource && (
          <p className="stats-busiest-resource">
            Busiest chapter recently:{' '}
            <Link to={`/chapters/${workspace.busiestResource.chapterId}`}>{workspace.busiestResource.name}</Link>{' '}
            ({formatDuration(workspace.busiestResource.activeSeconds)} active)
          </p>
        )}

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

      {workspace && (
        <section className="folder-section">
          <div className="folder-section-header">
            <div>
              <h2>When you write</h2>
              <p>Active writing time by day of week and hour, all-time.</p>
            </div>
          </div>
          <WritingHeatmap buckets={workspace.heatmap} />
        </section>
      )}

      {folderExtra && (
        <section className="folder-section">
          <div className="folder-section-header">
            <div>
              <h2>Stale chapters</h2>
              <p>Incomplete chapters with no writing activity in the last two weeks.</p>
            </div>
            {folderExtra.staleChapters.length > 0 && <span className="folder-count">{folderExtra.staleChapters.length}</span>}
          </div>
          {folderExtra.staleChapters.length === 0 ? (
            <p className="folder-empty-state">Nothing stale — everything's either recently active or marked complete.</p>
          ) : (
            <ul className="folder-item-list">
              {folderExtra.staleChapters.map((c) => (
                <li key={c.id}>
                  <div className="folder-item-name">
                    <Link to={`/chapters/${c.id}`}>{c.name}</Link>
                  </div>
                  <small>{c.daysSinceActivity} days inactive</small>
                  <button
                    type="button"
                    className="item-visibility-button"
                    onClick={() => fId !== undefined && toggleComplete.mutate({ chapterId: c.id, folderId: fId, completed: true })}
                  >
                    Mark complete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {folderExtra && (
        <section className="folder-section">
          <div className="folder-section-header">
            <div>
              <h2>Chapters in this sub-folder</h2>
              <p>Revisions, recent velocity, and WPM per chapter.</p>
            </div>
          </div>
          {folderExtra.wordCountSpread && (
            <div className="stats-tile-row">
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{folderExtra.wordCountSpread.min.toLocaleString()}</span>
                <span className="stats-summary-label">Shortest chapter</span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{folderExtra.wordCountSpread.avg.toLocaleString()}</span>
                <span className="stats-summary-label">Average chapter</span>
              </div>
              <div className="stats-summary-tile">
                <span className="stats-summary-value">{folderExtra.wordCountSpread.max.toLocaleString()}</span>
                <span className="stats-summary-label">Longest chapter</span>
              </div>
            </div>
          )}
          {folderExtra.chapters.length === 0 ? (
            <p className="folder-empty-state">No chapters yet.</p>
          ) : (
            <div className="stats-table-wrap">
              <table className="stats-table">
                <thead>
                  <tr>
                    <th>Chapter</th>
                    <th>Revisions</th>
                    <th>+words (7d)</th>
                    <th>+words (30d)</th>
                    <th>WPM</th>
                  </tr>
                </thead>
                <tbody>
                  {folderExtra.chapters.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/chapters/${c.id}`}>{c.name}</Link>
                      </td>
                      <td>{c.versionCount}</td>
                      <td>{c.recentVelocity7d.toLocaleString()}</td>
                      <td>{c.recentVelocity30d.toLocaleString()}</td>
                      <td>{c.wpm}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
