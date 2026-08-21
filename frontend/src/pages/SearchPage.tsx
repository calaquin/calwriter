import { Link, useSearchParams } from 'react-router-dom'
import { useSearch } from '../api/hooks'

export default function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q') || ''
  const { data: results, isLoading } = useSearch(q)

  return (
    <div>
      <h1>Search Results for "{q}"</h1>
      {isLoading && <p>Searching...</p>}
      {results && results.length > 0 && (
        <ul>
          {results.map((r, idx) => (
            <li key={`${r.id}-${r.matchType}-${idx}`}>
              <Link to={`/chapters/${r.id}`}>{r.name}</Link>
              {r.matchType === 'notes' && ' (in notes)'}
            </li>
          ))}
        </ul>
      )}
      {results && results.length === 0 && <p>No matches found.</p>}
    </div>
  )
}
