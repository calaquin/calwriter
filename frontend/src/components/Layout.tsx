import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import KeyboardShortcutsModal from './KeyboardShortcutsModal'
import { useSettings } from '../api/hooks'
import { SidebarVisibilityProvider } from '../context/SidebarVisibilityContext'
import { TabsProvider } from '../context/TabsContext'
import { ShortcutsModalProvider, useShortcutsModal } from '../context/ShortcutsModalContext'

function GlobalShortcutsListener() {
  const { open } = useShortcutsModal()
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault()
        open()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])
  return null
}

function ShortcutsModalHost() {
  const { isOpen, close } = useShortcutsModal()
  if (!isOpen) return null
  return <KeyboardShortcutsModal onClose={close} />
}

export default function Layout() {
  const { data: settings } = useSettings()

  // Old app set these as inline CSS vars on <body> server-side per request;
  // here we apply them imperatively to document.body since body lives
  // outside React's render tree.
  useEffect(() => {
    if (!settings) return
    document.body.classList.toggle('dark', settings.darkMode)
    const vars: Record<string, string> = settings.darkMode
      ? {
          '--sidebar-bg': settings.darkSidebarColor ?? '#333333',
          '--text-color': settings.darkTextColor ?? '#eeeeee',
          '--bg-color': settings.darkBgColor ?? '#222222',
          '--toolbar-bg': settings.darkToolbarColor ?? '#555555',
          '--editor-bg': settings.darkEditorColor ?? '#444444',
        }
      : {
          '--sidebar-bg': settings.sidebarColor,
          '--text-color': settings.textColor,
          '--bg-color': settings.bgColor,
          '--toolbar-bg': settings.toolbarColor,
          '--editor-bg': settings.editorColor,
        }
    for (const [k, v] of Object.entries(vars)) {
      document.body.style.setProperty(k, v)
    }
  }, [settings])

  return (
    <SidebarVisibilityProvider>
      <TabsProvider>
        <ShortcutsModalProvider>
          <GlobalShortcutsListener />
          <Sidebar />
          <div id="main">
            <Outlet />
          </div>
          <ShortcutsModalHost />
        </ShortcutsModalProvider>
      </TabsProvider>
    </SidebarVisibilityProvider>
  )
}
