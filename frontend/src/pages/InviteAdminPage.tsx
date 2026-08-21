import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCreateInvite } from '../api/hooks'
import { ApiError } from '../api/client'
import type { Invite } from '../api/types'

function formatExpiry(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function InviteAdminPage() {
  const createInvite = useCreateInvite()
  const [invite, setInvite] = useState<Invite | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const inviteUrl = invite ? `${window.location.origin}/invite/${invite.token}` : null

  async function handleGenerate() {
    setError(null)
    setCopied(false)
    try {
      const result = await createInvite.mutateAsync()
      setInvite(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create invite link')
    }
  }

  async function handleCopy() {
    if (!inviteUrl) return
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
    } catch {
      // Clipboard API unavailable -- the link is still selectable by hand.
    }
  }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            <Link to="/settings">&larr; Settings</Link>
          </div>
          <h1>Invite a user</h1>
        </div>
      </header>

      <section className="settings-panel">
        <div className="settings-panel-header">
          <div>
            <h2>Generate an invite link</h2>
            <p>
              Share this link with someone to let them create their own account. Each link works once and expires
              after 7 days.
            </p>
          </div>
        </div>

        {invite && inviteUrl && (
          <div className="invite-link-box">
            <input type="text" readOnly value={inviteUrl} onFocus={(e) => e.target.select()} />
            <button type="button" className="settings-secondary-action" onClick={handleCopy}>
              {copied ? 'Copied!' : 'Copy link'}
            </button>
          </div>
        )}
        {invite && <p className="invite-expiry">Expires {formatExpiry(invite.expiresAt)}</p>}

        {error && (
          <div className="settings-message error" role="alert">
            {error}
          </div>
        )}

        <div className="settings-form-actions">
          <button
            className="settings-primary-action"
            type="button"
            onClick={handleGenerate}
            disabled={createInvite.isPending}
          >
            {createInvite.isPending ? 'Generating…' : invite ? 'Generate another link' : 'Generate invite link'}
          </button>
        </div>
      </section>
    </div>
  )
}
