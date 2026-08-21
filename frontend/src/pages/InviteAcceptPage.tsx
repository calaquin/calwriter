import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api, ApiError } from '../api/client'
import type { Me } from '../api/types'

export default function InviteAcceptPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { setSession } = useAuth()

  const [checking, setChecking] = useState(true)
  const [invalidReason, setInvalidReason] = useState<string | null>(null)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) return
    api
      .get<{ expiresAt: string }>(`/invites/${token}`)
      .then(() => setChecking(false))
      .catch((err) => {
        setInvalidReason(err instanceof ApiError ? err.message : 'This invite link is not valid.')
        setChecking(false)
      })
  }, [token])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setSubmitting(true)
    try {
      const me = await api.post<Me>(`/invites/${token}/accept`, { username, password })
      setSession(me)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create account')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-box">
        <img src="/assets/favicon.ico" className="sidebar-icon" alt="CalWriter icon" />
        <h1 className="app-title">CalWriter</h1>

        {checking ? (
          <p>Checking invite link…</p>
        ) : invalidReason ? (
          <ul className="flashes">
            <li>{invalidReason}</li>
          </ul>
        ) : (
          <>
            <p className="invite-subtitle">
              You've been invited to CalWriter. Choose a username and password to create your account.
            </p>
            {error && (
              <ul className="flashes">
                <li>{error}</li>
              </ul>
            )}
            <form onSubmit={handleSubmit}>
              <input
                type="text"
                placeholder="Choose a username"
                autoFocus
                autoCapitalize="off"
                autoCorrect="off"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
              <input
                type="password"
                placeholder="Choose a password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
              <input
                type="password"
                placeholder="Confirm password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                minLength={8}
                required
              />
              <button type="submit" disabled={submitting}>
                {submitting ? 'Creating account…' : 'Create account'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
