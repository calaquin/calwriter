import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useBooks, useSettings } from '../api/hooks'
import { useAuth } from '../context/AuthContext'
import { useSidebarVisibility } from '../context/SidebarVisibilityContext'
import FolderTreeNode from './FolderTreeNode'

export default function Sidebar() {
  const { data: books } = useBooks()
  const { data: settings } = useSettings()
  const { user, logout } = useAuth()
  const { sidebarHidden, toggleSidebar } = useSidebarVisibility()
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState('')

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    navigate(`/search?q=${encodeURIComponent(query)}`)
  }

  // On narrow viewports the sidebar is an overlay (see index.css), so it
  // should get out of the way once you've actually navigated somewhere --
  // otherwise it just sits on top of the page you tapped through to. Guarded
  // against firing on the very first render (prevPathname starts equal), so
  // an explicit "leave it open" choice isn't immediately undone on mount.
  const prevPathname = useRef(location.pathname)
  useEffect(() => {
    if (prevPathname.current === location.pathname) return
    prevPathname.current = location.pathname
    if (!sidebarHidden && window.matchMedia('(max-width: 760px)').matches) {
      toggleSidebar()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const openBookIds = new Set(settings?.openBookIds ?? [])
  const closedFolderIds = new Set(settings?.closedFolderIds ?? [])
  const closedChapterIds = new Set(settings?.closedChapterIds ?? [])
  const openBooks = books?.filter((book) => openBookIds.has(book.id))

  if (sidebarHidden) {
    return (
      <div id="sidebar" className="collapsed">
        <button
          type="button"
          className="sidebar-reveal"
          onClick={toggleSidebar}
          title="Show sidebar"
          aria-label="Show sidebar"
        >
          ▶
        </button>
      </div>
    )
  }

  return (
    <div id="sidebar">
      <div className="sidebar-top">
        <Link to="/" className="sidebar-brand">
          <img src="/assets/favicon.ico" className="sidebar-icon" alt="CalWriter icon" />
          <span>CalWriter</span>
        </Link>
        <button
          type="button"
          className="sidebar-collapse"
          onClick={toggleSidebar}
          title="Hide sidebar"
          aria-label="Hide sidebar"
        >
          ◀
        </button>
      </div>
      {user && (
        <Link to="/changelog" className="version">
          v{user.version}
        </Link>
      )}
      <div className="sidebar-account">
        <span className="sidebar-username">{user?.username}</span>
        <div className="sidebar-account-links">
          <Link to="/settings">Settings</Link>
          <button type="button" className="link-button" onClick={() => logout()}>
            Logout
          </button>
        </div>
      </div>
      <form id="search_form" onSubmit={handleSearch}>
        <input type="text" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
      </form>
      <ul className="tree">
        {openBooks?.map((book) => (
          <FolderTreeNode
            key={book.id}
            folderId={book.id}
            name={book.name}
            level={0}
            parentId={null}
            role={book.role}
            color={book.color}
            closedFolderIds={closedFolderIds}
            closedChapterIds={closedChapterIds}
          />
        ))}
      </ul>
    </div>
  )
}
