import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useSearch, useInternalReferenceTargets } from '../api/hooks'
import type { SearchMatch, SearchScopeType } from '../api/types'

const RESULT_LIMIT = 50

const SOURCE_LABELS: Record<SearchMatch['source'], string> = {
  title: 'Title',
  content: 'Chapter',
  notes: 'Notes',
}

function scopeValue(scopeType: SearchScopeType, scopeId: string | null): string {
  return scopeType === 'workspace' ? 'workspace' : `${scopeType}:${scopeId}`
}

function parseScopeValue(value: string): { scopeType: SearchScopeType; scopeId: string | null } {
  if (value === 'workspace') return { scopeType: 'workspace', scopeId: null }
  const [scopeType, scopeId] = value.split(':') as [SearchScopeType, string]
  return { scopeType, scopeId }
}

/** Builds the match's jump-to-occurrence destination -- a title result opens
 * the chapter plainly, a content/notes result hands off the query text and
 * occurrence index (not raw offsets, which could be stale by the time this
 * is clicked -- see ChapterEditor's findRequest) as temporary URL params. */
function matchHref(match: SearchMatch, query: string): string {
  if (match.source === 'title') return `/chapters/${match.chapterId}`
  const params = new URLSearchParams({
    find: query,
    findSource: match.source,
    findIndex: String(match.occurrenceIndex ?? 0),
  })
  return `/chapters/${match.chapterId}?${params.toString()}`
}

/** Renders a snippet with its matched portion wrapped in a semantic <mark>
 * -- plain text only, never dangerouslySetInnerHTML (the API returns plain
 * text fragments specifically so this stays safe from injection). */
function Snippet({ match }: { match: SearchMatch }) {
  const { snippet } = match
  return (
    <p className="search-result-snippet">
      {snippet.leadingEllipsis && <span aria-hidden="true">…</span>}
      {snippet.before}
      <mark>{snippet.match}</mark>
      {snippet.after}
      {snippet.trailingEllipsis && <span aria-hidden="true">…</span>}
    </p>
  )
}

function SearchResultRow({ match, query }: { match: SearchMatch; query: string }) {
  return (
    <li className="search-result">
      <Link className="search-result-link" to={matchHref(match, query)}>
        <div className="search-result-heading">
          <span
            className="book-color-dot"
            style={{ backgroundColor: match.bookColor || '#999999' }}
            aria-hidden="true"
          />
          <span className="search-result-chapter-name">{match.chapterName}</span>
          <span className="search-result-source-badge">{SOURCE_LABELS[match.source]}</span>
        </div>
        <div className="search-result-book-name">{match.bookName}</div>
        <Snippet match={match} />
      </Link>
    </li>
  )
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const scopeType = (searchParams.get('scopeType') as SearchScopeType | null) ?? 'workspace'
  const scopeId = searchParams.get('scopeId')
  const offset = Number(searchParams.get('offset') ?? '0') || 0

  // Draft input text: only becomes the active `q` (and hits the API) on
  // submit -- search is user-triggered, not live-per-keystroke. Resynced
  // whenever `q` itself changes from elsewhere (Sidebar search, Back/
  // Forward, reload) -- not on every render, so it never fights normal
  // typing (submitting just sets `q` to what's already in the box).
  const [draftQuery, setDraftQuery] = useState(q)
  useEffect(() => setDraftQuery(q), [q])

  const { data: targets } = useInternalReferenceTargets(true)
  const scopeOptions = (targets ?? []).filter((t) => t.targetType !== 'chapter')

  const { data, isLoading, isError } = useSearch({ q, scopeType, scopeId, offset, limit: RESULT_LIMIT })

  function applyParams(next: { q?: string; scopeType?: SearchScopeType; scopeId?: string | null; offset?: number }) {
    const params = new URLSearchParams(searchParams)
    if (next.q !== undefined) {
      if (next.q) params.set('q', next.q)
      else params.delete('q')
    }
    if (next.scopeType !== undefined) {
      if (next.scopeType === 'workspace') {
        params.delete('scopeType')
        params.delete('scopeId')
      } else {
        params.set('scopeType', next.scopeType)
        if (next.scopeId) params.set('scopeId', next.scopeId)
      }
    }
    params.set('offset', String(next.offset ?? 0))
    setSearchParams(params)
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    applyParams({ q: draftQuery.trim(), offset: 0 })
  }

  function handleScopeChange(value: string) {
    const parsed = parseScopeValue(value)
    applyParams({ scopeType: parsed.scopeType, scopeId: parsed.scopeId, offset: 0 })
  }

  const matches = data?.matches ?? []
  const total = data?.totalMatches ?? 0
  const totalChapters = data?.totalChapters ?? 0
  const rangeStart = total === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(offset + matches.length, total)
  const countLabel =
    total === 0
      ? null
      : total > RESULT_LIMIT || offset > 0
        ? `Showing ${rangeStart.toLocaleString()}–${rangeEnd.toLocaleString()} of ${total.toLocaleString()} match${total === 1 ? '' : 'es'} in ${totalChapters.toLocaleString()} chapter${totalChapters === 1 ? '' : 's'}`
        : `${total.toLocaleString()} match${total === 1 ? '' : 'es'} in ${totalChapters.toLocaleString()} chapter${totalChapters === 1 ? '' : 's'}`

  return (
    <div className="folder-page search-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to="/">&larr; Books</Link>
          </div>
          <h1>Search</h1>
        </div>
      </header>

      <form className="search-controls" onSubmit={handleSubmit}>
        <label className="search-controls-field" htmlFor="search_page_query">
          <span>Search</span>
          <input
            id="search_page_query"
            type="text"
            value={draftQuery}
            onChange={(e) => setDraftQuery(e.target.value)}
            placeholder="Find text in chapters, notes, and titles…"
          />
        </label>
        <label className="search-controls-field search-controls-scope" htmlFor="search_page_scope">
          <span>Scope</span>
          <select
            id="search_page_scope"
            value={scopeValue(scopeType, scopeId)}
            onChange={(e) => handleScopeChange(e.target.value)}
          >
            <option value="workspace">Workspace</option>
            {scopeOptions.map((t) => (
              <option key={`${t.targetType}:${t.targetId}`} value={`${t.targetType}:${t.targetId}`}>
                {'  '.repeat(Math.max(0, t.depth - 1))}
                {t.targetType === 'book' ? `Book — ${t.name}` : `Folder — ${t.name} (${t.bookName})`}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="chapter-action primary search-controls-submit">
          Search
        </button>
      </form>

      <section className="folder-section stats-section">
        <div className="folder-section-header">
          <div>
            <h2>Results</h2>
            {countLabel && <p>{countLabel}</p>}
          </div>
        </div>

        {!q && <p className="folder-empty-state">Type something above to search your chapters, notes, and titles.</p>}
        {q && isLoading && <p className="folder-empty-state">Searching…</p>}
        {q && isError && <p className="folder-empty-state">Search is unavailable for that scope.</p>}
        {q && !isLoading && !isError && total === 0 && <p className="folder-empty-state">No matches found.</p>}

        {matches.length > 0 && (
          <ul className="search-result-list">
            {matches.map((m, idx) => (
              <SearchResultRow key={`${m.chapterId}-${m.source}-${m.occurrenceIndex ?? 0}-${idx}`} match={m} query={q} />
            ))}
          </ul>
        )}

        {total > RESULT_LIMIT && (
          <div className="search-pagination">
            <button
              type="button"
              className="chapter-action"
              disabled={offset === 0}
              onClick={() => applyParams({ offset: Math.max(0, offset - RESULT_LIMIT) })}
            >
              Previous
            </button>
            <button
              type="button"
              className="chapter-action"
              disabled={!data?.hasMore}
              onClick={() => applyParams({ offset: offset + RESULT_LIMIT })}
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
