import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, setCsrfToken } from '../api/client'
import type { Me } from '../api/types'

interface AuthContextValue {
  user: Me | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setSession: (me: Me) => void
  updateTimezone: (timezone: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<Me>('/auth/me')
      .then((me) => {
        setCsrfToken(me.csrfToken)
        setUser(me)
      })
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) {
          console.error('Failed to load session', e)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!user || user.timezone !== null) return
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (!detected) return
    api
      .patch<Me>('/me/timezone', { timezone: detected, onlyIfUnset: true })
      .then((updated) => {
        setCsrfToken(updated.csrfToken)
        setUser(updated)
      })
      .catch((e) => console.error('Failed to record browser timezone', e))
  }, [user])

  function setSession(me: Me) {
    setCsrfToken(me.csrfToken)
    setUser(me)
  }

  async function login(username: string, password: string) {
    const me = await api.post<Me>('/auth/login', { username, password })
    setSession(me)
  }

  async function logout() {
    await api.post<void>('/auth/logout')
    setCsrfToken(null)
    setUser(null)
  }

  async function updateTimezone(timezone: string) {
    const updated = await api.patch<Me>('/me/timezone', { timezone })
    setSession(updated)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setSession, updateTimezone }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
