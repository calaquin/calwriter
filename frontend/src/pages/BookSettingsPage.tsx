import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useBook, useUpdateBook } from '../api/hooks'
import { ApiError } from '../api/client'
import SharingSection from '../components/SharingSection'
import type { BookType } from '../api/types'

const BOOK_TYPE_OPTIONS: { value: BookType; label: string; description: string }[] = [
  { value: 'novel', label: 'Novel', description: 'Long-form creative writing with chapters and planning folders.' },
  { value: 'journal', label: 'Journal', description: 'Daily writing with one chapter per day, automatically organized by date.' },
  { value: 'documentation', label: 'Documentation', description: 'Documentation and reference writing.' },
  { value: 'general', label: 'General', description: 'A flexible book with no special behavior.' },
]

export default function BookSettingsPage() {
  const { folderId } = useParams()
  const bookId = folderId
  const { data: book, isLoading } = useBook(bookId)
  const update = useUpdateBook(bookId ?? '')

  const [name, setName] = useState('')
  const [author, setAuthor] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('#dddddd')
  const [showBookColor, setShowBookColor] = useState(true)
  const [bookType, setBookType] = useState<BookType>('general')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (book) {
      setName(book.name)
      setAuthor(book.author)
      setDescription(book.description)
      setColor(book.color || '#dddddd')
      setShowBookColor(book.showBookColor)
      setBookType(book.bookType)
    }
  }, [book])

  if (isLoading) return <p>Loading...</p>
  if (!book) return <p>Not found, or you don't have access to it.</p>
  if (book.role === 'viewer') return <p>You don't have permission to edit this book's settings.</p>

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setMessage(null)
    const trimmedName = name.trim()
    if (!trimmedName) {
      setMessage({ type: 'error', text: 'Title cannot be empty' })
      return
    }
    try {
      await update.mutateAsync({ name: trimmedName, author, description, color, showBookColor, bookType })
      setMessage({ type: 'success', text: 'Settings saved.' })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof ApiError ? err.message : 'Failed to save settings' })
    }
  }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to={`/folders/${bookId}`}>&larr; {book.name}</Link>
          </div>
          <h1>Book Settings</h1>
        </div>
        <div className="folder-page-actions">
          <Link className="folder-action" to={`/folders/${bookId}`}>
            Back to book
          </Link>
        </div>
      </header>

      <section className="settings-panel">
        <div className="settings-panel-header">
          <div>
            <h2>Details</h2>
            <p>Title, author, and description shown throughout the app.</p>
          </div>
        </div>
        <form className="book-settings-form" onSubmit={handleSubmit}>
          <fieldset className="book-type-selector">
            <legend>Book type</legend>
            <p className="book-type-selector-note">
              Book Type changes shortcuts and behavior. Changing it does not move or delete your existing content.
            </p>
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
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            <span>Author</span>
            <input type="text" value={author} onChange={(e) => setAuthor(e.target.value)} />
          </label>
          <label>
            <span>Description</span>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
          </label>

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

          <label className="chapter-complete-toggle">
            <input
              type="checkbox"
              checked={showBookColor}
              onChange={(e) => setShowBookColor(e.target.checked)}
            />
            Use book color as a subtle editor background
          </label>

          {message && (
            <div className={`settings-message ${message.type}`} role={message.type === 'error' ? 'alert' : 'status'}>
              {message.text}
            </div>
          )}

          <div className="settings-form-actions">
            <button className="settings-primary-action" type="submit" disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </form>
      </section>

      {book.role === 'owner' && (
        <section className="settings-panel">
          <div className="settings-panel-header">
            <div>
              <h2>Sharing</h2>
              <p>Invite someone to read or edit this book.</p>
            </div>
          </div>
          <SharingSection resourceType="folder" resourceId={book.id} resourceNoun="book" showHeading={false} />
        </section>
      )}
    </div>
  )
}
