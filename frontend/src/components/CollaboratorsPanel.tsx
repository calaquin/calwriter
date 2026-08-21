import { useState, type FormEvent } from 'react'
import { useCollaborators, useAddCollaborator, useRemoveCollaborator } from '../api/hooks'
import { ApiError } from '../api/client'

export default function CollaboratorsPanel({ bookId }: { bookId: number }) {
  const { data: collaborators } = useCollaborators(bookId)
  const add = useAddCollaborator(bookId)
  const remove = useRemoveCollaborator(bookId)
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<'editor' | 'viewer'>('viewer')
  const [error, setError] = useState<string | null>(null)

  async function handleAdd(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await add.mutateAsync({ username, role })
      setUsername('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to share book')
    }
  }

  return (
    <section className="folder-section sharing-section">
      <div className="folder-section-header">
        <div>
          <h2>Sharing</h2>
          <p>Invite someone to read or edit this book.</p>
        </div>
        <span className="folder-count">{collaborators?.length ?? 0}</span>
      </div>
      {collaborators && collaborators.length === 0 && <p className="folder-empty-state">Not shared with anyone yet.</p>}
      {collaborators && collaborators.length > 0 && (
        <ul className="sharing-list">
          {collaborators.map((c) => (
            <li key={c.userId}>
              <div className="collaborator-name">
                <span>{c.username}</span>
                <small>{c.role === 'editor' ? 'Can edit' : 'Read only'}</small>
              </div>
              <button type="button" className="item-remove-button" onClick={() => remove.mutate(c.userId)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <ul className="flashes">
          <li>{error}</li>
        </ul>
      )}
      <form onSubmit={handleAdd} className="share-form">
        <input type="text" aria-label="Username" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <select value={role} onChange={(e) => setRole(e.target.value as 'editor' | 'viewer')}>
          <option value="viewer">Viewer (read-only)</option>
          <option value="editor">Editor (can edit)</option>
        </select>
        <button type="submit" disabled={add.isPending}>Share book</button>
      </form>
    </section>
  )
}
