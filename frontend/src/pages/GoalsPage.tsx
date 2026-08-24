import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useGoals, useCreateGoal, useUpdateGoal, useDeleteGoal, useSettings, useUpdateSettings } from '../api/hooks'
import { useDragReorder } from '../hooks/useDragReorder'
import { EMPTY_ARRAY } from '../api/constants'
import type { Goal, GoalResourceType } from '../api/types'
import CreateGoalModal from '../components/CreateGoalModal'
import EditGoalModal from '../components/EditGoalModal'
import ConfirmModal from '../components/ConfirmModal'
import GoalCard from '../components/GoalCard'

function applyOrder(goals: Goal[], order: string[]): Goal[] {
  const orderIndex = new Map(order.map((id, i) => [id, i]))
  return [...goals].sort((a, b) => {
    const ai = orderIndex.has(a.id) ? orderIndex.get(a.id)! : Infinity
    const bi = orderIndex.has(b.id) ? orderIndex.get(b.id)! : Infinity
    return ai - bi
  })
}

export default function GoalsPage() {
  const { data: goals, isLoading } = useGoals()
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const createGoal = useCreateGoal()
  const updateGoal = useUpdateGoal()
  const deleteGoal = useDeleteGoal()
  const [searchParams, setSearchParams] = useSearchParams()
  const [newGoalResource, setNewGoalResource] = useState<{ type: GoalResourceType; id: string } | undefined>()
  const [showCreate, setShowCreate] = useState(false)
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [showHidden, setShowHidden] = useState(false)

  // Arriving via a resource's "⋯ > Goals" link carries which resource that
  // was, so "New goal" opens pre-scoped to it -- but landing here should
  // never itself pop the create modal open unprompted.
  useEffect(() => {
    const resourceType = searchParams.get('resourceType')
    const resourceId = searchParams.get('resourceId')
    if ((resourceType !== 'folder' && resourceType !== 'chapter') || !resourceId) return
    setNewGoalResource({ type: resourceType, id: resourceId })
    const next = new URLSearchParams(searchParams)
    next.delete('resourceType')
    next.delete('resourceId')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const hiddenIds = new Set(settings?.hiddenGoalIds ?? [])
  const orderedGoals = goals ? applyOrder(goals, settings?.goalOrder ?? []) : []
  const visibleGoals = orderedGoals.filter((g) => !hiddenIds.has(g.id))
  const hiddenGoals = orderedGoals.filter((g) => hiddenIds.has(g.id))

  const { order: dragOrder, onDragStart, onDragOver, onDrop } = useDragReorder(visibleGoals ?? EMPTY_ARRAY, (newOrder) => {
    // Persist the full order, not just the visible slice, so a hidden
    // goal's relative position survives a drag of the visible list.
    updateSettings.mutate({ goalOrder: [...newOrder, ...hiddenGoals.map((g) => g.id)] })
  })

  function openCreate() {
    setNewGoalResource(undefined)
    setShowCreate(true)
  }

  function handleCreate(data: Parameters<typeof createGoal.mutate>[0]) {
    createGoal.mutate(data, { onSuccess: () => setShowCreate(false) })
  }

  function handleSaveEdit(data: { target: number; startDate?: string; endDate?: string; name?: string }) {
    if (!editingGoal) return
    updateGoal.mutate({ goalId: editingGoal.id, ...data }, { onSuccess: () => setEditingGoal(null) })
  }

  function toggleHidden(goalId: string, isHidden: boolean) {
    const current = settings?.hiddenGoalIds ?? []
    updateSettings.mutate({
      hiddenGoalIds: isHidden ? current.filter((id) => id !== goalId) : [...current, goalId],
    })
  }

  function togglePrimary(goalId: string) {
    updateSettings.mutate({ primaryGoalId: settings?.primaryGoalId === goalId ? null : goalId })
  }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to="/">&larr; Books</Link>
          </div>
          <h1>Goals</h1>
        </div>
        <div className="folder-page-actions">
          <button type="button" className="home-wizard-action" onClick={openCreate}>
            New goal
          </button>
        </div>
      </header>

      <section className="folder-section">
        {isLoading && <p className="folder-empty-state">Loading…</p>}
        {!isLoading && goals && goals.length === 0 && (
          <div className="home-empty-state">
            <strong>No goals yet</strong>
            <span>Set a words-written or chapter-completion target to start tracking progress.</span>
          </div>
        )}
        {!isLoading && visibleGoals.length > 0 && (
          <ul className="goal-list sortable">
            {dragOrder.map((goal, idx) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                hidden={false}
                isPrimary={settings?.primaryGoalId === goal.id}
                onEdit={() => setEditingGoal(goal)}
                onDelete={() => setDeletingId(goal.id)}
                onToggleHidden={() => toggleHidden(goal.id, false)}
                onTogglePrimary={() => togglePrimary(goal.id)}
                dragHandleProps={{
                  draggable: true,
                  onDragStart: () => onDragStart(idx),
                  onDragOver: (e) => onDragOver(idx, e),
                  onDrop,
                }}
              />
            ))}
          </ul>
        )}
        {!isLoading && goals && goals.length > 0 && visibleGoals.length === 0 && (
          <p className="folder-empty-state">All goals are hidden.</p>
        )}

        {hiddenGoals.length > 0 && (
          <>
            <button
              type="button"
              className="modal-section-toggle goals-hidden-toggle"
              onClick={() => setShowHidden((v) => !v)}
              aria-expanded={showHidden}
            >
              <span>Hidden goals ({hiddenGoals.length})</span>
              <span className="modal-section-toggle-icon" aria-hidden="true">
                {showHidden ? '▾' : '▸'}
              </span>
            </button>
            {showHidden && (
              <ul className="goal-list">
                {hiddenGoals.map((goal) => (
                  <GoalCard
                    key={goal.id}
                    goal={goal}
                    hidden
                    isPrimary={settings?.primaryGoalId === goal.id}
                    onEdit={() => setEditingGoal(goal)}
                    onDelete={() => setDeletingId(goal.id)}
                    onToggleHidden={() => toggleHidden(goal.id, true)}
                    onTogglePrimary={() => togglePrimary(goal.id)}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {showCreate && (
        <CreateGoalModal
          resource={newGoalResource}
          saving={createGoal.isPending}
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
        />
      )}
      {editingGoal && (
        <EditGoalModal
          goal={editingGoal}
          saving={updateGoal.isPending}
          onClose={() => setEditingGoal(null)}
          onSave={handleSaveEdit}
        />
      )}
      {deletingId !== null && (
        <ConfirmModal
          title="Delete goal"
          message="Delete this goal? This cannot be undone."
          confirmLabel="Delete"
          pending={deleteGoal.isPending}
          onConfirm={() => deleteGoal.mutate(deletingId, { onSuccess: () => setDeletingId(null) })}
          onCancel={() => setDeletingId(null)}
        />
      )}
    </div>
  )
}
