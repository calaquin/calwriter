import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

const OPEN_TABS_KEY = 'calwriter:openTabs'

export interface OpenTab {
  chapterId: number
  name: string
  folderId: number
  folderAccessible: boolean
  bookId: number
}

interface TabsContextValue {
  tabs: OpenTab[]
  openTab: (tab: OpenTab) => void
  closeTab: (chapterId: number) => void
  closeTabsForBook: (bookId: number) => void
}

const TabsContext = createContext<TabsContextValue | null>(null)

function loadTabs(): OpenTab[] {
  try {
    const raw = localStorage.getItem(OPEN_TABS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveTabs(tabs: OpenTab[]) {
  try {
    localStorage.setItem(OPEN_TABS_KEY, JSON.stringify(tabs))
  } catch {
    // Tabs stay session-only if storage is unavailable.
  }
}

export function TabsProvider({ children }: { children: ReactNode }) {
  const [tabs, setTabs] = useState<OpenTab[]>(loadTabs)

  const openTab = useCallback((tab: OpenTab) => {
    setTabs((prev) => {
      const idx = prev.findIndex((t) => t.chapterId === tab.chapterId)
      if (idx === -1) {
        const next = [...prev, tab]
        saveTabs(next)
        return next
      }
      if (
        prev[idx].name !== tab.name ||
        prev[idx].folderId !== tab.folderId ||
        prev[idx].folderAccessible !== tab.folderAccessible ||
        prev[idx].bookId !== tab.bookId
      ) {
        const next = [...prev]
        next[idx] = tab
        saveTabs(next)
        return next
      }
      return prev
    })
  }, [])

  const closeTab = useCallback((chapterId: number) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.chapterId !== chapterId)
      saveTabs(next)
      return next
    })
  }, [])

  const closeTabsForBook = useCallback((bookId: number) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.bookId !== bookId)
      if (next.length === prev.length) return prev
      saveTabs(next)
      return next
    })
  }, [])

  return (
    <TabsContext.Provider value={{ tabs, openTab, closeTab, closeTabsForBook }}>{children}</TabsContext.Provider>
  )
}

export function useTabs() {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('useTabs must be used within a TabsProvider')
  return ctx
}
