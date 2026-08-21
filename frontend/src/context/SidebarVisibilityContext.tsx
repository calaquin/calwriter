import { createContext, useContext, useState, type ReactNode } from 'react'

const SIDEBAR_HIDDEN_KEY = 'calwriter:sidebarHidden'
// Below this width the sidebar becomes an overlay (see index.css) rather than
// pushing content aside, so it defaults to collapsed here -- but only when
// the user has never explicitly chosen a state; an explicit choice always wins.
const MOBILE_BREAKPOINT_QUERY = '(max-width: 760px)'

interface SidebarVisibilityContextValue {
  sidebarHidden: boolean
  toggleSidebar: () => void
}

const SidebarVisibilityContext = createContext<SidebarVisibilityContextValue | null>(null)

export function SidebarVisibilityProvider({ children }: { children: ReactNode }) {
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_HIDDEN_KEY)
      if (stored !== null) return stored === 'true'
      return window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
    } catch {
      return false
    }
  })

  function toggleSidebar() {
    setSidebarHidden((hidden) => {
      const next = !hidden
      try {
        localStorage.setItem(SIDEBAR_HIDDEN_KEY, String(next))
      } catch {
        // The preference can remain session-only if storage is unavailable.
      }
      return next
    })
  }

  return (
    <SidebarVisibilityContext.Provider value={{ sidebarHidden, toggleSidebar }}>
      {children}
    </SidebarVisibilityContext.Provider>
  )
}

export function useSidebarVisibility() {
  const ctx = useContext(SidebarVisibilityContext)
  if (!ctx) throw new Error('useSidebarVisibility must be used within a SidebarVisibilityProvider')
  return ctx
}
