import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useBook, useUpdateBook } from '../api/hooks'
import { ApiError } from '../api/client'

export default function BookSettingsPage() {
  const { folderId } = useParams()
  const bookId = folderId ? Number(folderId) : undefined
  const { data: book, isLoading } = useBook(bookId)
  const update = useUpdateBook(bookId ?? 0)

  const [name, setName] = useState('')
  const [author, setAuthor] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('#dddddd')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (book) {
      setName(book.name)
      setAuthor(book.author)
      setDescription(book.description)
      setColor(book.color || '#dddddd')
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
      await update.mutateAsync({ name: trimmedName, author, description, color })
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
    </div>
  )
}
