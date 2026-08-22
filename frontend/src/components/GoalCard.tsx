import { Link } from 'react-router-dom'
import type { DragEvent } from 'react'
import type { Goal } from '../api/types'

const CADENCE_LABEL: Record<string, string> = { daily: 'day', weekly: 'week', monthly: 'month' }
const MS_PER_DAY = 86400000

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function daysBetween(fromIso: string, toIso: string): number {
  const from = new Date(`${fromIso}T00:00:00`)
  const to = new Date(`${toIso}T00:00:00`)
  return Math.round((to.getTime() - from.getTime()) / MS_PER_DAY)
}

export function goalDescription(goal: Goal): string {
  const unit = goal.goalType === 'words' ? 'words' : 'chapters'
  if (goal.cadence) {
    const base = `${goal.target.toLocaleString()} ${unit} / ${CADENCE_LABEL[goal.cadence]}`
    return goal.endDate ? `${base} until ${formatDate(goal.endDate)}` : base
  }
  return `${goal.target.toLocaleString()} ${unit} by ${goal.endDate ? formatDate(goal.endDate) : '?'}`
}

function resourceBadge(goal: Goal): string {
  if (goal.resourceType === 'chapter') return 'Chapter'
  return goal.resourceIsBook ? 'Book' : 'Sub-folder'
}

/** Pace stats: how fast progress is actually happening vs. how fast it
 * needs to happen to still hit the target before the period ends. Only
 * meaningful once a goal has started and isn't already achieved. */
function paceStats(goal: Goal) {
  if (!goal.started || goal.achieved || !goal.periodEnd) return null
  const todayIso = new Date().toISOString().slice(0, 10)
  const unit = goal.goalType === 'words' ? 'words' : 'chapters'
  const daysElapsed = Math.max(1, daysBetween(goal.periodStart, todayIso) + 1)
  const daysRemaining = Math.max(0, daysBetween(todayIso, goal.periodEnd) + 1)
  const paceSoFar = goal.current / daysElapsed
  const remaining = Math.max(0, goal.target - goal.current)
  const paceNeeded = daysRemaining > 0 ? remaining / daysRemaining : null
  const onTrack = paceNeeded !== null && paceSoFar >= paceNeeded
  return { unit, paceSoFar, paceNeeded, daysRemaining, onTrack }
}

interface DragHandleProps {
  draggable: true
  onDragStart: () => void
  onDragOver: (e: DragEvent<HTMLLIElement>) => void
  onDrop: () => void
}

export default function GoalCard({
  goal,
  hidden,
  onEdit,
  onDelete,
  onToggleHidden,
  dragHandleProps,
}: {
  goal: Goal
  hidden: boolean
  onEdit: () => void
  onDelete: () => void
  onToggleHidden: () => void
  /** Present only for goals in the draggable visible list. */
  dragHandleProps?: DragHandleProps
}) {
  const pace = paceStats(goal)

  return (
    <li className={`goal-card${hidden ? ' goal-card-hidden' : ''}`} {...(dragHandleProps ?? {})}>
      {dragHandleProps && (
        <span className="drag-handle" aria-hidden="true">
          ⋮⋮
        </span>
      )}
      <div className="goal-card-main">
        {goal.name && <p className="goal-card-name">{goal.name}</p>}
        <div className="goal-card-heading">
          <span className="goal-card-badge">{resourceBadge(goal)}</span>
          {goal.resourceBreadcrumb.map((crumb) => (
            <span key={crumb.id} className="goal-card-crumb">
              <Link to={`/folders/${crumb.id}`} style={crumb.color ? { color: crumb.color } : undefined}>
                {crumb.name}
              </Link>
              <span className="goal-card-crumb-sep" aria-hidden="true">
                ›
              </span>
            </span>
          ))}
          {goal.resourceAccessible ? (
            <Link
              to={goal.resourceType === 'folder' ? `/folders/${goal.resourceId}` : `/chapters/${goal.resourceId}`}
              style={goal.resourceColor ? { color: goal.resourceColor } : undefined}
            >
              {goal.resourceName ?? 'Untitled'}
            </Link>
          ) : (
            <span>{goal.resourceName ?? 'No longer accessible'}</span>
          )}
        </div>
        <p className="goal-card-desc">{goalDescription(goal)}</p>
        {goal.started ? (
          <>
            <div className="goal-progress-track">
              <div
                className={`goal-progress-fill${goal.achieved ? ' achieved' : ''}`}
                style={{ width: `${Math.max(2, goal.percent)}%` }}
              />
            </div>
            <span className="goal-progress-label">
              {goal.current.toLocaleString()} / {goal.target.toLocaleString()} ({goal.percent}%)
              {goal.achieved && ' ✓ Achieved'}
            </span>
            {pace && (
              <div className="goal-pace-row">
                <span className={`goal-pace-badge${pace.onTrack ? ' on-track' : ' behind'}`}>
                  {pace.onTrack ? 'On track' : 'Behind pace'}
                </span>
                <span className="goal-pace-stat">{pace.paceSoFar.toFixed(1)} {pace.unit}/day so far</span>
                <span className="goal-pace-stat">
                  {pace.paceNeeded !== null ? `${pace.paceNeeded.toFixed(1)} ${pace.unit}/day needed` : 'Period ended'}
                </span>
                <span className="goal-pace-stat">
                  {pace.daysRemaining} {pace.daysRemaining === 1 ? 'day' : 'days'} left
                </span>
              </div>
            )}
          </>
        ) : (
          <span className="goal-progress-label">Starts {formatDate(goal.periodStart)}</span>
        )}
      </div>
      <div className="goal-card-actions">
        {goal.cadence && (
          <Link className="folder-action" to={`/goals/${goal.id}/history`}>
            History
          </Link>
        )}
        <button type="button" className="folder-action" onClick={onToggleHidden}>
          {hidden ? 'Show' : 'Hide'}
        </button>
        <button type="button" className="folder-action" onClick={onEdit}>
          Edit
        </button>
        <button type="button" className="item-remove-button" onClick={onDelete}>
          Delete
        </button>
      </div>
    </li>
  )
}
