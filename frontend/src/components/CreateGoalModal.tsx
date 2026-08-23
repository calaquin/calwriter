import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useBooks, useFolder, useChapter, useFolderTree } from '../api/hooks'
import type { GoalCadence, GoalResourceType, GoalType } from '../api/types'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function addDaysIso(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const CADENCE_OPTIONS: { value: GoalCadence; label: string }[] = [
  { value: 'daily', label: 'Every day' },
  { value: 'weekly', label: 'Every week' },
  { value: 'monthly', label: 'Every month' },
]

/** depth-indented "folder:123" / "chapter:456" key, or '' for the book itself. */
function targetKeyOf(type: GoalResourceType, id: string): string {
  return `${type}:${id}`
}

export default function CreateGoalModal({
  resource,
  saving,
  onClose,
  onCreate,
}: {
  /** Fixed target resource, e.g. arriving from a sidebar "⋯ > Goals" link.
   * When omitted, the modal lets the user pick a book, then optionally
   * narrow to any sub-folder or chapter within it. */
  resource?: { type: GoalResourceType; id: string }
  saving: boolean
  onClose: () => void
  onCreate: (data: {
    resourceType: GoalResourceType
    resourceId: string
    goalType: GoalType
    target: number
    cadence?: GoalCadence
    startDate?: string
    endDate?: string
    name?: string
  }) => void
}) {
  const { data: books } = useBooks()
  const { data: folder } = useFolder(resource?.type === 'folder' ? resource.id : undefined)
  const { data: chapter } = useChapter(resource?.type === 'chapter' ? resource.id : undefined)
  const [selectedBookId, setSelectedBookId] = useState<string | null>(null)
  const { data: treeEntries } = useFolderTree(!resource ? (selectedBookId ?? undefined) : undefined)
  const [targetKey, setTargetKey] = useState('') // '' = whole book
  const [name, setName] = useState('')
  const [goalType, setGoalType] = useState<GoalType>('words')
  const [target, setTarget] = useState('500')
  const [timeframe, setTimeframe] = useState<'recurring' | 'fixed'>('recurring')
  const [cadence, setCadence] = useState<GoalCadence>('weekly')
  const [startDate, setStartDate] = useState(todayIso())
  const [endDate, setEndDate] = useState(addDaysIso(7))
  /** Separate from `endDate` (the fixed-range "To" field) -- a recurring
   * goal's end is optional and defaults to blank (never ends). */
  const [recurringEndDate, setRecurringEndDate] = useState('')
  const firstInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!resource && books && books.length > 0 && selectedBookId === null) {
      setSelectedBookId(books[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [books, resource])

  // Switching books invalidates whichever sub-folder/chapter was picked in
  // the previous one.
  useEffect(() => {
    setTargetKey('')
  }, [selectedBookId])

  useEffect(() => {
    firstInputRef.current?.focus()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const pickedEntry = !resource && targetKey ? treeEntries?.find((e) => targetKeyOf(e.type, e.id) === targetKey) : undefined

  const resourceType: GoalResourceType = resource?.type ?? pickedEntry?.type ?? 'folder'
  const resourceId = resource ? resource.id : (pickedEntry?.id ?? selectedBookId)
  const resourceLabel = resource
    ? resource.type === 'folder'
      ? folder?.name
      : chapter?.name
    : (pickedEntry?.name ?? books?.find((b) => b.id === selectedBookId)?.name)

  // A "chapters completed" goal only makes sense on a folder (book or
  // sub-folder); if the resource picker moves to a chapter, that goal type
  // is no longer valid.
  useEffect(() => {
    if (resourceType === 'chapter') setGoalType('words')
  }, [resourceType])

  const targetNumber = Number(target)
  const canSubmit =
    resourceId !== null &&
    Number.isInteger(targetNumber) &&
    targetNumber > 0 &&
    startDate &&
    (timeframe === 'recurring'
      ? !recurringEndDate || recurringEndDate >= startDate
      : endDate && endDate >= startDate)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit || resourceId === null) return
    onCreate({
      resourceType,
      resourceId,
      goalType,
      target: targetNumber,
      cadence: timeframe === 'recurring' ? cadence : undefined,
      startDate,
      endDate: timeframe === 'fixed' ? endDate : recurringEndDate || undefined,
      name: name.trim() || undefined,
    })
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog wizard-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-goal-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="create-goal-modal-title">New goal</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="book-settings-form" onSubmit={handleSubmit}>
          {resource ? (
            <div className="goal-modal-resource">
              <span>Goal for</span>
              <strong>{resourceLabel ?? 'Loading…'}</strong>
            </div>
          ) : (
            <>
              <label>
                <span>Book</span>
                <select value={selectedBookId ?? ''} onChange={(e) => setSelectedBookId(e.target.value)}>
                  {(books ?? []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              {treeEntries && treeEntries.length > 0 && (
                <label>
                  <span>Scope within book</span>
                  <select value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
                    <option value="">Whole book</option>
                    {treeEntries.map((entry) => (
                      <option key={targetKeyOf(entry.type, entry.id)} value={targetKeyOf(entry.type, entry.id)}>
                        {'  '.repeat(entry.depth)}
                        {entry.type === 'chapter' ? '📄 ' : '📁 '}
                        {entry.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </>
          )}

          <label>
            <span>Name (optional)</span>
            <input
              type="text"
              placeholder="e.g. First draft push"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>

          <div className="wizard-extras">
            <span>Goal type</span>
            <div className="wizard-extras-chips">
              <button
                type="button"
                className={`wizard-extra-chip${goalType === 'words' ? ' active' : ''}`}
                aria-pressed={goalType === 'words'}
                onClick={() => setGoalType('words')}
              >
                Word count
              </button>
              {resourceType === 'folder' && (
                <button
                  type="button"
                  className={`wizard-extra-chip${goalType === 'chapters' ? ' active' : ''}`}
                  aria-pressed={goalType === 'chapters'}
                  onClick={() => setGoalType('chapters')}
                >
                  Chapters completed
                </button>
              )}
            </div>
          </div>

          <label>
            <span>Target ({goalType === 'words' ? 'words' : 'chapters'})</span>
            <input
              ref={firstInputRef}
              type="number"
              min={1}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
          </label>

          <div className="wizard-extras">
            <span>Timeframe</span>
            <div className="wizard-extras-chips">
              <button
                type="button"
                className={`wizard-extra-chip${timeframe === 'recurring' ? ' active' : ''}`}
                aria-pressed={timeframe === 'recurring'}
                onClick={() => setTimeframe('recurring')}
              >
                Recurring
              </button>
              <button
                type="button"
                className={`wizard-extra-chip${timeframe === 'fixed' ? ' active' : ''}`}
                aria-pressed={timeframe === 'fixed'}
                onClick={() => setTimeframe('fixed')}
              >
                Fixed date range
              </button>
            </div>
          </div>

          {timeframe === 'recurring' ? (
            <>
              <label>
                <span>Repeats</span>
                <select value={cadence} onChange={(e) => setCadence(e.target.value as GoalCadence)}>
                  {CADENCE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="goal-modal-date-row">
                <label>
                  <span>Starts</span>
                  <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </label>
                <label>
                  <span>Ends (optional)</span>
                  <input
                    type="date"
                    value={recurringEndDate}
                    onChange={(e) => setRecurringEndDate(e.target.value)}
                    min={startDate}
                  />
                </label>
              </div>
            </>
          ) : (
            <div className="goal-modal-date-row">
              <label>
                <span>From</span>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </label>
              <label>
                <span>To</span>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={startDate} />
              </label>
            </div>
          )}

          <div className="settings-form-actions">
            <button type="button" className="settings-secondary-action" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="settings-primary-action" disabled={saving || !canSubmit}>
              {saving ? 'Creating…' : 'Create goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
