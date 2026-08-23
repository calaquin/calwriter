import { Link, useSearchParams } from 'react-router-dom'
import { useSearch, useBooks } from '../api/hooks'

export default function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q') || ''
  const { data: results, isLoading } = useSearch(q)
  const { data: books } = useBooks()
  const bookById = new Map(books?.map((b) => [b.id, b]))

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to="/">&larr; Books</Link>
          </div>
          <h1>{q ? `Results for "${q}"` : 'Search'}</h1>
        </div>
      </header>

      <section className="folder-section">
        <div className="folder-section-header">
          <div>
            <h2>Chapters</h2>
            <p>Matches in chapter content or notes.</p>
          </div>
          {results && results.length > 0 && <span className="folder-count">{results.length}</span>}
        </div>
        {!q && <p className="folder-empty-state">Type something in the sidebar search box to find chapters.</p>}
        {q && isLoading && <p className="folder-empty-state">Searching…</p>}
        {q && results && results.length === 0 && <p className="folder-empty-state">No matches found.</p>}
        {results && results.length > 0 && (
          <ul className="folder-item-list">
            {results.map((r, idx) => {
              const book = bookById.get(r.bookId)
              return (
                <li key={`${r.id}-${r.matchType}-${idx}`}>
                  <span
                    className="book-color-dot"
                    style={{ backgroundColor: book?.color || '#999999' }}
                    aria-hidden="true"
                  />
                  <div className="folder-item-name">
                    <Link to={`/chapters/${r.id}`}>{r.name}</Link>
                    {book && <small>{book.name}</small>}
                  </div>
                  {r.matchType === 'notes' && <span className="goal-card-badge">Notes</span>}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
