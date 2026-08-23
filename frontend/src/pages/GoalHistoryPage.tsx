import { Link, useParams } from 'react-router-dom'
import { useGoalHistory } from '../api/hooks'

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function GoalHistoryPage() {
  const { goalId } = useParams()
  const id = goalId
  const { data, isLoading } = useGoalHistory(id)
  const goal = data?.goal
  const periods = data?.periods ?? []
  const chartPeriods = [...periods].reverse()

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to="/goals">&larr; Goals</Link>
          </div>
          <h1>{goal ? goal.name || goal.resourceName || 'Goal' : 'Goal'} History</h1>
          {goal && <p className="folder-author">{goal.resourceName}</p>}
        </div>
      </header>

      <section className="folder-section stats-section">
        {isLoading && <p className="folder-empty-state">Loading…</p>}
        {!isLoading && periods.length === 0 && (
          <p className="folder-empty-state">
            No completed periods yet -- history starts accumulating once this goal's first period ends.
          </p>
        )}
        {!isLoading && chartPeriods.length > 0 && (
          <div className="stats-chart">
            {chartPeriods.map((p) => (
              <div key={p.id} className="stats-bar-column">
                <span className="stats-bar-count">{p.current.toLocaleString()}</span>
                <div
                  className={`stats-bar goal-history-bar${p.achieved ? ' achieved' : ''}`}
                  style={{ height: `${Math.max(4, p.percent)}%` }}
                  title={`${p.current.toLocaleString()} / ${p.target.toLocaleString()} (${p.percent}%)`}
                />
                <span className="stats-bar-day">{formatDate(p.periodStart)}</span>
              </div>
            ))}
          </div>
        )}
        {!isLoading && periods.length > 0 && (
          <ul className="goal-history-list">
            {periods.map((p) => (
              <li key={p.id}>
                <span>
                  {formatDate(p.periodStart)} – {formatDate(p.periodEnd)}
                </span>
                <span>
                  {p.current.toLocaleString()} / {p.target.toLocaleString()} ({p.percent}%)
                </span>
                <span className={`goal-pace-badge${p.achieved ? ' on-track' : ' behind'}`}>
                  {p.achieved ? 'Achieved' : 'Missed'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
