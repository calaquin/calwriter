import { createContext, useContext, useState, type ReactNode } from 'react'

interface ShortcutsModalContextValue {
  isOpen: boolean
  open: () => void
  close: () => void
}

const ShortcutsModalContext = createContext<ShortcutsModalContextValue | null>(null)

export function ShortcutsModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <ShortcutsModalContext.Provider value={{ isOpen, open: () => setIsOpen(true), close: () => setIsOpen(false) }}>
      {children}
    </ShortcutsModalContext.Provider>
  )
}

export function useShortcutsModal() {
  const ctx = useContext(ShortcutsModalContext)
  if (!ctx) throw new Error('useShortcutsModal must be used within a ShortcutsModalProvider')
  return ctx
}
