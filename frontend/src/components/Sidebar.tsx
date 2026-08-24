import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useBooks, useGoals, useSettings, useSharedWithMe, useLeaveShare } from '../api/hooks'
import { useAuth } from '../context/AuthContext'
import { useSidebarVisibility } from '../context/SidebarVisibilityContext'
import { useTabs } from '../context/TabsContext'
import FolderTreeNode from './FolderTreeNode'
import TreeItemMenu from './TreeItemMenu'
import ConfirmModal from './ConfirmModal'
import { goalDescription, goalProgressUnit } from './GoalCard'
import type { SharedItem } from '../api/types'

export default function Sidebar() {
  const { data: books } = useBooks()
  const { data: settings } = useSettings()
  const { data: goals } = useGoals()
  const { data: sharedItems } = useSharedWithMe()
  const { lastVisited } = useTabs()
  const leaveShare = useLeaveShare()
  const { user, logout } = useAuth()
  const { sidebarHidden, toggleSidebar } = useSidebarVisibility()
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [leaveTarget, setLeaveTarget] = useState<SharedItem | null>(null)

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

  const primaryGoal = goals?.find((g) => g.id === settings?.primaryGoalId)
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
      {primaryGoal && (
        <Link
          to="/goals"
          className="sidebar-primary-goal"
          title={`${primaryGoal.name || primaryGoal.resourceName || 'Goal'} -- ${goalDescription(primaryGoal)}`}
        >
          <div className="sidebar-primary-goal-header">
            <span className="sidebar-primary-goal-star" aria-hidden="true">★</span>
            <span className="sidebar-primary-goal-name">
              {primaryGoal.name || primaryGoal.resourceName || 'Goal'}
            </span>
          </div>
          {primaryGoal.started ? (
            <>
              <div className="goal-progress-track">
                <div
                  className={`goal-progress-fill${primaryGoal.achieved ? ' achieved' : ''}`}
                  style={{ width: `${Math.max(2, primaryGoal.percent)}%` }}
                />
              </div>
              <span className="goal-progress-label">
                {primaryGoal.current.toLocaleString()} / {primaryGoal.target.toLocaleString()}{' '}
                {goalProgressUnit(primaryGoal)} ({primaryGoal.percent}%)
                {primaryGoal.achieved && ' ✓'}
              </span>
            </>
          ) : (
            <span className="goal-progress-label">Starts soon</span>
          )}
        </Link>
      )}
      {lastVisited && location.pathname !== `/chapters/${lastVisited.chapterId}` && (
        <Link
          to={`/chapters/${lastVisited.chapterId}`}
          className="sidebar-resume-link"
          title={`Continue writing: ${lastVisited.name}`}
        >
          <span className="sidebar-resume-icon" aria-hidden="true">
            ✎
          </span>
          <span className="sidebar-resume-text">Continue: {lastVisited.name}</span>
        </Link>
      )}
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
      {sharedItems && sharedItems.length > 0 && (
        <>
          <div className="sidebar-section-label">Shared with me</div>
          <ul className="tree">
            {sharedItems.map((item) => {
              function leave() {
                setLeaveTarget(item)
              }
              return item.type === 'folder' ? (
                <FolderTreeNode
                  key={`shared-folder-${item.id}`}
                  folderId={item.id}
                  name={item.name}
                  level={0}
                  parentId={item.parentId}
                  role={item.role}
                  isBook={false}
                  closedFolderIds={closedFolderIds}
                  closedChapterIds={closedChapterIds}
                  extraMenuActions={[{ label: 'Leave', danger: true, separatorBefore: true, onClick: leave }]}
                />
              ) : (
                <li key={`shared-chapter-${item.id}`} className="tree-item chapter-item shared-item">
                  <Link to={`/chapters/${item.id}`}>{item.name}</Link>
                  <small className="shared-item-book" title={item.bookName}>
                    {item.bookName}
                  </small>
                  <TreeItemMenu actions={[{ label: 'Leave', danger: true, onClick: leave }]} />
                </li>
              )
            })}
          </ul>
        </>
      )}
      {leaveTarget && (
        <ConfirmModal
          title={`Leave ${leaveTarget.type === 'folder' ? 'folder' : 'chapter'}`}
          message={`Remove "${leaveTarget.name}" from your sidebar? You can be re-shared with it later.`}
          confirmLabel="Leave"
          pending={leaveShare.isPending}
          onConfirm={() => {
            if (!user) return
            leaveShare.mutate(
              { resourceType: leaveTarget.type, resourceId: leaveTarget.id, userId: user.id },
              { onSuccess: () => setLeaveTarget(null) },
            )
          }}
          onCancel={() => setLeaveTarget(null)}
        />
      )}
    </div>
  )
}
