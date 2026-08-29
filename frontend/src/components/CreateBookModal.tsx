import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useCreateBookWizard } from '../api/hooks'
import { ApiError } from '../api/client'
import type { Book, BookType } from '../api/types'

const EXTRA_OPTIONS = ['Characters', 'Factions', 'Locations']

const BOOK_TYPE_OPTIONS: { value: BookType; label: string; description: string }[] = [
  { value: 'novel', label: 'Novel', description: 'Long-form creative writing with chapters and planning folders.' },
  { value: 'journal', label: 'Journal', description: 'Daily writing with one chapter per day, automatically organized by date.' },
  { value: 'documentation', label: 'Documentation', description: 'Documentation and reference writing.' },
  { value: 'general', label: 'General', description: 'A flexible book with no special behavior.' },
]

export default function CreateBookModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (book: Book) => void
}) {
  const wizard = useCreateBookWizard()
  const [bookType, setBookType] = useState<BookType>('novel')
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [chapters, setChapters] = useState('Chapters')
  const [color, setColor] = useState('#dddddd')
  const [extras, setExtras] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const titleRef = useRef<HTMLInputElement>(null)
  const isNovel = bookType === 'novel'

  useEffect(() => {
    titleRef.current?.focus()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function toggleExtra(name: string) {
    setExtras((prev) => (prev.includes(name) ? prev.filter((e) => e !== name) : [...prev, name]))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) return
    setError(null)
    try {
      const book = await wizard.mutateAsync({
        title: trimmed,
        author,
        color,
        bookType,
        // Novel-specific scaffolding is only meaningful (and only sent)
        // for a Novel -- other types create just the root book.
        ...(isNovel ? { chapters, extras } : {}),
      })
      onCreated(book)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create book')
    }
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog wizard-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="wizard-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="wizard-modal-title">New book</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="book-settings-form" onSubmit={handleSubmit}>
          <fieldset className="book-type-selector">
            <legend>Book type</legend>
            <div className="book-type-options">
              {BOOK_TYPE_OPTIONS.map((opt) => (
                <label key={opt.value} className={`book-type-option${bookType === opt.value ? ' active' : ''}`}>
                  <input
                    type="radio"
                    name="bookType"
                    value={opt.value}
                    checked={bookType === opt.value}
                    onChange={() => setBookType(opt.value)}
                  />
                  <span className="book-type-option-label">{opt.label}</span>
                  <span className="book-type-option-description">{opt.description}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label>
            <span>Title</span>
            <input
              ref={titleRef}
              type="text"
              placeholder="Book title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>
          <label>
            <span>Author</span>
            <input
              type="text"
              placeholder="Author name"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
            />
          </label>
          {isNovel && (
            <label>
              <span>Chapters folder</span>
              <input type="text" value={chapters} onChange={(e) => setChapters(e.target.value)} />
            </label>
          )}

          <label className="color-setting">
            <span className="color-setting-copy">
              <strong>Color</strong>
              <small>Used for this book's sidebar title and dot indicator</small>
            </span>
            <span className="color-setting-control">
              <input type="color" value={color} onChange={(e) => setColor(e.target.value)} aria-label="Book color" />
              <code>{color.toUpperCase()}</code>
            </span>
          </label>

          {isNovel && (
            <div className="wizard-extras">
              <span>Additional folders</span>
              <div className="wizard-extras-chips">
                {EXTRA_OPTIONS.map((name) => {
                  const active = extras.includes(name)
                  return (
                    <button
                      key={name}
                      type="button"
                      className={`wizard-extra-chip${active ? ' active' : ''}`}
                      aria-pressed={active}
                      onClick={() => toggleExtra(name)}
                    >
                      {name}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {error && (
            <div className="settings-message error" role="alert">
              {error}
            </div>
          )}

          <div className="settings-form-actions">
            <button type="button" className="settings-secondary-action" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="settings-primary-action" disabled={wizard.isPending || !title.trim()}>
              {wizard.isPending ? 'Creating…' : 'Create book'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
