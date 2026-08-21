import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export interface MenuAction {
  label: string
  onClick?: () => void
  danger?: boolean
  separatorBefore?: boolean
  submenu?: { label: string; onClick: () => void }[]
}

interface Position {
  top: number
  left: number
}

const MENU_WIDTH = 200
const SUBMENU_WIDTH = 180

// The sidebar scrolls its own content (overflow-y: auto), which forces
// overflow-x: auto too per the CSS spec -- any absolutely-positioned
// descendant that tries to extend past its bounds gets silently clipped.
// Rendering the menu into a portal at document.body, positioned with fixed
// pixel coordinates from the trigger's own rect, sidesteps that entirely.
export default function TreeItemMenu({ actions }: { actions: MenuAction[] }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<Position | null>(null)
  const [submenu, setSubmenu] = useState<{ label: string; position: Position } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const submenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: MouseEvent) {
      const target = e.target as Node
      if (
        triggerRef.current?.contains(target) ||
        menuRef.current?.contains(target) ||
        submenuRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
      setSubmenu(null)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        setSubmenu(null)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function toggleOpen() {
    if (open) {
      setOpen(false)
      setSubmenu(null)
      return
    }
    const rect = triggerRef.current?.getBoundingClientRect()
    if (rect) {
      setPosition({ top: rect.bottom + 2, left: Math.min(rect.right - MENU_WIDTH, window.innerWidth - MENU_WIDTH - 8) })
    }
    setOpen(true)
  }

  function openSubmenu(label: string, rowEl: HTMLElement) {
    const rect = rowEl.getBoundingClientRect()
    const left =
      rect.right + SUBMENU_WIDTH + 8 <= window.innerWidth ? rect.right + 4 : rect.left - SUBMENU_WIDTH - 4
    setSubmenu({ label, position: { top: rect.top - 4, left } })
  }

  function closeAll() {
    setOpen(false)
    setSubmenu(null)
  }

  return (
    <div className="tree-item-menu">
      <button
        ref={triggerRef}
        type="button"
        className="tree-item-menu-trigger"
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          toggleOpen()
        }}
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        ⋯
      </button>
      {open &&
        position &&
        createPortal(
          <div
            ref={menuRef}
            className="tree-item-menu-list"
            role="menu"
            style={{ position: 'fixed', top: position.top, left: position.left }}
            onClick={(e) => e.stopPropagation()}
          >
            {actions.map((action) => (
              <div key={action.label}>
                {action.separatorBefore && <div className="tree-item-menu-divider" role="separator" />}
                {action.submenu ? (
                  <div
                    className="tree-item-menu-row tree-item-menu-row-parent"
                    onMouseEnter={(e) => openSubmenu(action.label, e.currentTarget)}
                    onClick={(e) => openSubmenu(action.label, e.currentTarget)}
                  >
                    <span>{action.label}</span>
                    <span className="tree-item-menu-chevron" aria-hidden="true">
                      ›
                    </span>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={`tree-item-menu-row${action.danger ? ' danger' : ''}`}
                    role="menuitem"
                    onClick={() => {
                      action.onClick?.()
                      closeAll()
                    }}
                  >
                    {action.label}
                  </button>
                )}
              </div>
            ))}
          </div>,
          document.body,
        )}
      {open &&
        submenu &&
        createPortal(
          <div
            ref={submenuRef}
            className="tree-item-menu-submenu"
            role="menu"
            style={{ position: 'fixed', top: submenu.position.top, left: submenu.position.left }}
            onClick={(e) => e.stopPropagation()}
          >
            {actions
              .find((a) => a.label === submenu.label)
              ?.submenu?.map((sub) => (
                <button
                  key={sub.label}
                  type="button"
                  className="tree-item-menu-row"
                  role="menuitem"
                  onClick={() => {
                    sub.onClick()
                    closeAll()
                  }}
                >
                  {sub.label}
                </button>
              ))}
          </div>,
          document.body,
        )}
    </div>
  )
}
