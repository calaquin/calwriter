import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useBookStats } from '../api/hooks'

export default function StatsPage() {
  const { folderId } = useParams()
  const id = folderId ? Number(folderId) : undefined
  const [days, setDays] = useState(7)
  const { data: stats, isLoading } = useBookStats(id, days)

  const entries = stats ? Object.entries(stats.wordsPerDay).sort(([a], [b]) => a.localeCompare(b)) : []
  const maxCount = Math.max(1, ...entries.map(([, count]) => count))

  return (
    <div>
      <h1>Stats</h1>
      {isLoading && <p>Loading...</p>}
      {stats && <p>Total words: {stats.totalWords}</p>}
      <h2>Words per day</h2>
      <form onSubmit={(e) => e.preventDefault()} style={{ marginBottom: '1em' }}>
        <label>
          Days to show:{' '}
          <input
            type="number"
            min={1}
            value={days}
            onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
          />
        </label>
      </form>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '200px' }}>
        {entries.map(([day, count]) => (
          <div key={day} style={{ textAlign: 'center', fontSize: '0.8em' }}>
            <div
              title={`${count} words`}
              style={{
                width: '30px',
                height: `${(count / maxCount) * 160}px`,
                background: 'var(--toolbar-bg)',
                border: '1px solid #ccc',
              }}
            />
            <div>{count}</div>
            <div>{day.slice(5)}</div>
          </div>
        ))}
        {entries.length === 0 && !isLoading && <p>No data yet.</p>}
      </div>
      <p style={{ marginTop: '1em' }}>
        <Link to={`/folders/${id}`}>Back to Book</Link>
      </p>
    </div>
  )
}
