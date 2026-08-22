import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { Goal } from '../api/types'

const CADENCE_LABEL: Record<string, string> = { daily: 'Every day', weekly: 'Every week', monthly: 'Every month' }

export default function EditGoalModal({
  goal,
  saving,
  onClose,
  onSave,
}: {
  goal: Goal
  saving: boolean
  onClose: () => void
  onSave: (data: { target: number; startDate?: string; endDate?: string; name?: string }) => void
}) {
  const [name, setName] = useState(goal.name)
  const [target, setTarget] = useState(String(goal.target))
  const [startDate, setStartDate] = useState(goal.startDate)
  const [endDate, setEndDate] = useState(goal.endDate ?? '')
  const firstInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    firstInputRef.current?.focus()
    firstInputRef.current?.select()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const isFixedRange = goal.cadence === null
  const targetNumber = Number(target)
  const changed =
    targetNumber !== goal.target ||
    startDate !== goal.startDate ||
    endDate !== (goal.endDate ?? '') ||
    name.trim() !== goal.name
  const canSubmit =
    Number.isInteger(targetNumber) &&
    targetNumber > 0 &&
    changed &&
    (isFixedRange ? endDate !== '' && endDate >= startDate : endDate === '' || endDate >= startDate)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    // Only send fields that actually changed -- startDate/endDate in the
    // payload at all tells the backend to re-anchor the goal's current
    // period and clear its progress baseline, so an unrelated edit (just
    // the target, say) must not carry along the unchanged date. An empty
    // endDate is meaningful too (for a recurring goal): it clears a
    // previously-set end back to "never ends".
    const data: { target: number; startDate?: string; endDate?: string; name?: string } = { target: targetNumber }
    if (startDate !== goal.startDate) data.startDate = startDate
    if (endDate !== (goal.endDate ?? '')) data.endDate = endDate
    if (name.trim() !== goal.name) data.name = name.trim()
    onSave(data)
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog wizard-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-goal-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="edit-goal-modal-title">Edit goal</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="book-settings-form" onSubmit={handleSubmit}>
          <div className="goal-modal-resource">
            <span>Goal for</span>
            <strong>{goal.resourceName ?? 'Untitled'}</strong>
          </div>

          <div className="goal-modal-resource">
            <span>Timeframe</span>
            <strong>{goal.cadence ? CADENCE_LABEL[goal.cadence] : 'Fixed range'}</strong>
          </div>

          <label>
            <span>Name (optional)</span>
            <input
              ref={firstInputRef}
              type="text"
              placeholder="e.g. First draft push"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>

          <label>
            <span>Target ({goal.goalType === 'words' ? 'words' : 'chapters'})</span>
            <input type="number" min={1} value={target} onChange={(e) => setTarget(e.target.value)} />
          </label>

          <div className="goal-modal-date-row">
            <label>
              <span>Starts</span>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} max={endDate || undefined} />
            </label>
            <label>
              <span>Ends{isFixedRange ? '' : ' (optional)'}</span>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={startDate} />
            </label>
          </div>

          <div className="settings-form-actions">
            <button type="button" className="settings-secondary-action" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="settings-primary-action" disabled={saving || !canSubmit}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
