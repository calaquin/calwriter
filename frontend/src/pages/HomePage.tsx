import { useRef, useState, type ChangeEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useBooks,
  useSettings,
  useUpdateSettings,
  useReorderBooks,
  useExportDatabase,
  useImportDatabase,
} from '../api/hooks'
import { useDragReorder } from '../hooks/useDragReorder'
import { EMPTY_ARRAY } from '../api/constants'
import { ApiError } from '../api/client'
import { useTabs } from '../context/TabsContext'
import CreateBookModal from '../components/CreateBookModal'

export default function HomePage() {
  const { data: books, isLoading } = useBooks()
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const reorderBooks = useReorderBooks()
  const exportDb = useExportDatabase()
  const importDb = useImportDatabase()
  const navigate = useNavigate()
  const { closeTabsForBook } = useTabs()
  const [showCreate, setShowCreate] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { order, onDragStart, onDragOver, onDrop } = useDragReorder(books ?? EMPTY_ARRAY, (ids) => reorderBooks.mutate(ids))
  const openBookIds = new Set(settings?.openBookIds ?? [])

  function toggleBookOpen(bookId: string, isOpen: boolean) {
    const current = settings?.openBookIds ?? []
    const nextIds = isOpen ? current.filter((id) => id !== bookId) : [...current, bookId]
    updateSettings.mutate({ openBookIds: nextIds })
    if (isOpen) closeTabsForBook(bookId)
  }

  async function handleImportFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setImportError(null)
    try {
      await importDb.mutateAsync(file)
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : 'Import failed')
    }
  }

  return (
    <div className="home-page">
      <header className="home-page-header">
        <div>
          <div className="home-eyebrow">Your workspace</div>
          <h1>Books</h1>
          <p>Pick up where you left off or start something new.</p>
        </div>
        <div className="folder-page-actions">
          <Link className="folder-action" to="/goals">Goals</Link>
          <Link className="folder-action" to="/stats">Stats</Link>
          <button type="button" className="home-wizard-action" onClick={() => setShowCreate(true)}>New book</button>
        </div>
      </header>

      {showCreate && (
        <CreateBookModal
          onClose={() => setShowCreate(false)}
          onCreated={(book) => {
            setShowCreate(false)
            navigate(`/folders/${book.id}`)
          }}
        />
      )}

      <section className="home-library-section">
        <div className="home-section-header">
          <div>
            <h2>Your library</h2>
            <p>Drag books to change their sidebar order.</p>
          </div>
          <span className="folder-count">{books?.length ?? 0}</span>
        </div>
        {isLoading && <p className="home-loading">Loading books…</p>}
        {!isLoading && order.length > 0 && (
          <ul className="home-book-list sortable">
            {order.map((book, idx) => {
              const isOpen = openBookIds.has(book.id)
              return (
                <li
                  key={book.id}
                  draggable
                  onDragStart={() => onDragStart(idx)}
                  onDragOver={(e) => onDragOver(idx, e)}
                  onDrop={onDrop}
                >
                  <span className="drag-handle" aria-hidden="true">⋮⋮</span>
                  <span className="book-color-dot" style={{ backgroundColor: book.color || '#999999' }} aria-hidden="true" />
                  <div className="home-book-name">
                    <div>
                      {isOpen ? <Link to={`/folders/${book.id}`}>{book.name}</Link> : <span>{book.name}</span>}
                      {book.role !== 'owner' && <span className="book-role">{book.role}</span>}
                    </div>
                    <small>
                      {book.author && `by ${book.author} · `}
                      {isOpen ? 'Shown in sidebar' : 'Hidden from sidebar'}
                    </small>
                  </div>
                  <button type="button" className="item-visibility-button" onClick={() => toggleBookOpen(book.id, isOpen)}>
                    {isOpen ? 'Close' : 'Open'}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        {!isLoading && books && books.length === 0 && (
          <div className="home-empty-state">
            <strong>No books yet</strong>
            <span>Create your first book to get started.</span>
          </div>
        )}
      </section>

      <section className="home-tools-section">
        <div className="home-section-header">
          <div>
            <h2>Backup and restore</h2>
            <p>Keep a portable copy of your CalWriter library.</p>
          </div>
        </div>
        {importError && (
          <ul className="flashes">
            <li>{importError}</li>
          </ul>
        )}
        <div className="database-tools-grid">
          <div className="database-tool">
            <div>
              <h3>Export library</h3>
              <p>Download all of your books as a <code>.calwdb</code> backup.</p>
            </div>
            <button type="button" onClick={() => exportDb.mutate()} disabled={exportDb.isPending}>
              {exportDb.isPending ? 'Exporting…' : 'Export backup'}
            </button>
          </div>
          <div className="database-tool">
            <div>
              <h3>Import library</h3>
              <p>Restore books from an existing <code>.calwdb</code> file.</p>
            </div>
            <input type="file" accept=".calwdb" ref={fileInputRef} onChange={handleImportFile} />
            <button type="button" onClick={() => fileInputRef.current?.click()} disabled={importDb.isPending}>
              {importDb.isPending ? 'Importing…' : 'Choose backup'}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
