import { useState, type FormEvent } from 'react'
import { useShares, useAddShare, useUpdateShare, useRemoveShare } from '../api/hooks'
import { ApiError } from '../api/client'

export default function SharingSection({
  resourceType,
  resourceId,
  resourceNoun,
  showHeading = true,
  collapsible = false,
}: {
  resourceType: 'folder' | 'chapter'
  resourceId: number
  /** What to call this in the UI, e.g. "book", "sub-folder", "chapter". */
  resourceNoun: string
  /** Set false when an enclosing section already has its own "Sharing" heading. */
  showHeading?: boolean
  /** Start collapsed behind a "Sharing" toggle instead of always showing the
   * collaborator list and add-share form -- for embedding inside a settings
   * modal, where sharing isn't usually what someone opened it to do. Only
   * takes effect when showHeading is true. */
  collapsible?: boolean
}) {
  const [expanded, setExpanded] = useState(!collapsible)
  const { data: shares } = useShares(resourceType, resourceId)
  const add = useAddShare(resourceType, resourceId)
  const update = useUpdateShare(resourceType, resourceId)
  const remove = useRemoveShare(resourceType, resourceId)
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<'editor' | 'viewer'>('viewer')
  const [error, setError] = useState<string | null>(null)
  const showBody = !showHeading || expanded

  async function handleAdd(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await add.mutateAsync({ username, role })
      setUsername('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to share')
    }
  }

  return (
    <div className="modal-section">
      {showHeading &&
        (collapsible ? (
          <button
            type="button"
            className="modal-section-toggle"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            <span>Sharing{shares && shares.length > 0 ? ` (${shares.length})` : ''}</span>
            <span className="modal-section-toggle-icon" aria-hidden="true">
              {expanded ? '▾' : '▸'}
            </span>
          </button>
        ) : (
          <label>Sharing</label>
        ))}
      {showBody && (
        <>
          {shares && shares.length === 0 && <p className="folder-empty-state">Not shared with anyone yet.</p>}
          {shares && shares.length > 0 && (
            <ul className="sharing-list">
              {shares.map((s) => (
                <li key={s.userId}>
                  <div className="collaborator-name">
                    <span>{s.username}</span>
                  </div>
                  <select
                    value={s.role}
                    aria-label={`Role for ${s.username}`}
                    onChange={(e) => update.mutate({ userId: s.userId, role: e.target.value as 'editor' | 'viewer' })}
                  >
                    <option value="viewer">Viewer (read-only)</option>
                    <option value="editor">Editor (can edit)</option>
                  </select>
                  <button type="button" className="item-remove-button" onClick={() => remove.mutate(s.userId)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          {error && (
            <div className="settings-message error" role="alert">
              {error}
            </div>
          )}
          <form onSubmit={handleAdd} className="share-form">
            <input
              type="text"
              aria-label="Username"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <select value={role} onChange={(e) => setRole(e.target.value as 'editor' | 'viewer')}>
              <option value="viewer">Viewer (read-only)</option>
              <option value="editor">Editor (can edit)</option>
            </select>
            <button type="submit" disabled={add.isPending}>
              Share {resourceNoun}
            </button>
          </form>
        </>
      )}
    </div>
  )
}
