import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useInternalReferenceTargets } from '../api/hooks'
import type { InternalReferenceTarget } from '../api/types'

function normalizeExternalUrl(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const candidate = /^[a-z][a-z\d+.-]*:/i.test(trimmed) ? trimmed : `https://${trimmed}`
  try {
    const parsed = new URL(candidate)
    return ['http:', 'https:', 'mailto:'].includes(parsed.protocol) ? parsed.href : null
  } catch {
    return null
  }
}

export default function LinkDialog({
  selectedText,
  onClose,
  onExternal,
  onInternal,
}: {
  selectedText: string
  onClose: () => void
  onExternal: (url: string) => void
  onInternal: (target: InternalReferenceTarget) => void
}) {
  const [kind, setKind] = useState<'internal' | 'external'>('internal')
  const [query, setQuery] = useState('')
  const [url, setUrl] = useState('')
  const [urlError, setUrlError] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  const { data: targets = [], isLoading, error } = useInternalReferenceTargets(true)

  useEffect(() => {
    searchRef.current?.focus()
  }, [kind])

  useEffect(() => {
    function closeWithEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', closeWithEscape)
    return () => document.removeEventListener('keydown', closeWithEscape)
  }, [onClose])

  const filteredTargets = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    if (!needle) return targets
    return targets.filter((target) =>
      `${target.name} ${target.bookName} ${target.targetType}`.toLocaleLowerCase().includes(needle),
    )
  }, [query, targets])

  function submitExternal(e: FormEvent) {
    e.preventDefault()
    const normalized = normalizeExternalUrl(url)
    if (!normalized) {
      setUrlError('Enter an http, https, or email link.')
      return
    }
    onExternal(normalized)
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog link-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="link-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="link-dialog-title">Add link</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <p className="link-dialog-selection" title={selectedText}>Linking “{selectedText}”</p>
        <div className="link-kind-tabs" role="tablist" aria-label="Link type">
          <button
            type="button"
            role="tab"
            aria-selected={kind === 'internal'}
            className={kind === 'internal' ? 'active' : ''}
            onClick={() => setKind('internal')}
          >
            CalWriter item
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={kind === 'external'}
            className={kind === 'external' ? 'active' : ''}
            onClick={() => setKind('external')}
          >
            External URL
          </button>
        </div>

        {kind === 'internal' ? (
          <div className="link-picker-panel" role="tabpanel">
            <label htmlFor="internal-reference-search">Search books, folders, and chapters</label>
            <input
              id="internal-reference-search"
              ref={searchRef}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search CalWriter…"
            />
            <div className="internal-reference-tree" role="tree" aria-label="CalWriter items">
              {isLoading && <p className="link-picker-status">Loading…</p>}
              {error && <p className="link-picker-status error">Could not load items.</p>}
              {!isLoading && !error && filteredTargets.length === 0 && (
                <p className="link-picker-status">No matching items.</p>
              )}
              {filteredTargets.map((target) => (
                <button
                  key={`${target.targetType}:${target.targetId}`}
                  type="button"
                  role="treeitem"
                  className="internal-reference-option"
                  style={{ paddingLeft: `${12 + target.depth * 18}px` }}
                  onClick={() => onInternal(target)}
                  title={`${target.targetType} in ${target.bookName}`}
                >
                  <span className={`internal-reference-type ${target.targetType}`} aria-hidden="true" />
                  <span className="internal-reference-name">{target.name}</span>
                  <small>{target.targetType}</small>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <form className="link-picker-panel" role="tabpanel" onSubmit={submitExternal}>
            <label htmlFor="external-link-url">URL</label>
            <input
              id="external-link-url"
              ref={searchRef}
              type="text"
              inputMode="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                setUrlError('')
              }}
              placeholder="https://example.com"
            />
            {urlError && <p className="link-form-error">{urlError}</p>}
            <button type="submit" className="chapter-action primary" disabled={!url.trim()}>Add link</button>
          </form>
        )}
      </div>
    </div>
  )
}
