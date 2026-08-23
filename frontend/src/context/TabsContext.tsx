import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

// v2: chapter/folder/book ids became UUID strings -- bumped so a stale
// pre-migration entry (numeric ids) is simply never read again rather than
// rehydrating into tabs that can never match anything.
const OPEN_TABS_KEY = 'calwriter:openTabs:v2'
const LAST_VISITED_KEY = 'calwriter:lastVisitedChapter'

// Keeps the tab strip from growing without bound across a long session --
// opening past this many auto-closes the oldest (tabs[0], since new ones are
// always appended at the end) rather than requiring manual cleanup.
const MAX_OPEN_TABS = 7

export interface OpenTab {
  chapterId: string
  name: string
  folderId: string
  folderAccessible: boolean
  bookId: string
}

/** One auto-close notification, for the toast in ChapterTabs. `key` is a
 * fresh id per eviction (not just the tab name) so the toast's display timer
 * restarts even if the very next eviction happens to name the same chapter. */
interface AutoClosedNotice {
  key: number
  name: string
}

interface TabsContextValue {
  tabs: OpenTab[]
  openTab: (tab: OpenTab) => void
  closeTab: (chapterId: string) => void
  closeTabsForBook: (bookId: string) => void
  lastAutoClosed: AutoClosedNotice | null
  /** The chapter most recently opened, for the sidebar's "resume" link --
   * unlike `tabs` (ordered by when each was FIRST opened), this always
   * reflects whichever chapter was visited most recently, persists across
   * reloads, and survives that chapter's tab being closed. */
  lastVisited: OpenTab | null
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

function loadLastVisited(): OpenTab | null {
  try {
    const raw = localStorage.getItem(LAST_VISITED_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveLastVisited(tab: OpenTab) {
  try {
    localStorage.setItem(LAST_VISITED_KEY, JSON.stringify(tab))
  } catch {
    // Falls back to session-only if storage is unavailable.
  }
}

export function TabsProvider({ children }: { children: ReactNode }) {
  const [tabs, setTabs] = useState<OpenTab[]>(loadTabs)
  const [lastAutoClosed, setLastAutoClosed] = useState<AutoClosedNotice | null>(null)
  const [lastVisited, setLastVisited] = useState<OpenTab | null>(loadLastVisited)
  const noticeCounter = useRef(0)

  // Reads `tabs` directly (not the setTabs(prev => ...) functional-updater
  // form used elsewhere in this file) specifically so the eviction decision
  // can be made -- and lastAutoClosed set -- in the same synchronous pass as
  // computing the new tab list. A functional updater's callback runs on
  // React's own schedule, not inline, so anything it computes (like which
  // tab got evicted) isn't available to code right after the setTabs() call.
  const openTab = useCallback(
    (tab: OpenTab) => {
      setLastVisited(tab)
      saveLastVisited(tab)
      const idx = tabs.findIndex((t) => t.chapterId === tab.chapterId)
      if (idx === -1) {
        const appended = [...tabs, tab]
        if (appended.length > MAX_OPEN_TABS) {
          const evicted = appended[0]
          const next = appended.slice(appended.length - MAX_OPEN_TABS)
          saveTabs(next)
          setTabs(next)
          noticeCounter.current += 1
          setLastAutoClosed({ key: noticeCounter.current, name: evicted.name })
        } else {
          saveTabs(appended)
          setTabs(appended)
        }
        return
      }
      const current = tabs[idx]
      if (
        current.name !== tab.name ||
        current.folderId !== tab.folderId ||
        current.folderAccessible !== tab.folderAccessible ||
        current.bookId !== tab.bookId
      ) {
        const next = [...tabs]
        next[idx] = tab
        saveTabs(next)
        setTabs(next)
      }
    },
    [tabs],
  )

  const closeTab = useCallback((chapterId: string) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.chapterId !== chapterId)
      saveTabs(next)
      return next
    })
  }, [])

  const closeTabsForBook = useCallback((bookId: string) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.bookId !== bookId)
      if (next.length === prev.length) return prev
      saveTabs(next)
      return next
    })
  }, [])

  return (
    <TabsContext.Provider value={{ tabs, openTab, closeTab, closeTabsForBook, lastAutoClosed, lastVisited }}>
      {children}
    </TabsContext.Provider>
  )
}

export function useTabs() {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('useTabs must be used within a TabsProvider')
  return ctx
}
