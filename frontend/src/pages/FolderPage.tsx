import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  useFolder,
  useFolderTreeIds,
  useBook,
  useUpdateFolder,
  useDeleteFolder,
  useCreateFolder,
  useCreateChapter,
  useReorderFolderChildren,
  useSettings,
  useUpdateSettings,
  useLeaveShare,
  useOpenAll,
  useToggleChapterComplete,
} from '../api/hooks'
import { useDragReorder } from '../hooks/useDragReorder'
import { EMPTY_ARRAY } from '../api/constants'
import { useAuth } from '../context/AuthContext'
import { triggerDownload } from '../api/client'
import FolderSettingsModal from '../components/FolderSettingsModal'
import CreateItemModal from '../components/CreateItemModal'
import ConfirmModal from '../components/ConfirmModal'
import TreeItemMenu, { type MenuAction } from '../components/TreeItemMenu'

export default function FolderPage() {
  const { folderId } = useParams()
  const id = folderId
  const { data: folder, isLoading, error } = useFolder(id)
  const { data: treeIds } = useFolderTreeIds(id)
  const { data: settings } = useSettings()
  const isBook = folder?.parentId === null
  const { data: book } = useBook(isBook ? id : undefined)
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [showSettings, setShowSettings] = useState(false)
  const [creating, setCreating] = useState<'folder' | 'chapter' | null>(null)
  const [confirmAction, setConfirmAction] = useState<'delete' | 'leave' | null>(null)

  useEffect(() => {
    if (searchParams.get('settings') !== '1') return
    setShowSettings(true)
    const next = new URLSearchParams(searchParams)
    next.delete('settings')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const update = useUpdateFolder(id ?? '', folder?.parentId ?? null)
  const del = useDeleteFolder(folder?.parentId ?? null)
  const createFolder = useCreateFolder(id ?? '')
  const createChapter = useCreateChapter(id ?? '')
  const reorder = useReorderFolderChildren(id ?? '')
  const updateSettings = useUpdateSettings()
  const leaveShare = useLeaveShare()
  const openAll = useOpenAll()
  const toggleComplete = useToggleChapterComplete()

  const subfolderDrag = useDragReorder(folder?.folders ?? EMPTY_ARRAY, (order) => reorder.mutate({ type: 'folder', order }))
  const chapterDrag = useDragReorder(folder?.chapters ?? EMPTY_ARRAY, (order) => reorder.mutate({ type: 'chapter', order }))
  const closedFolderIds = new Set(settings?.closedFolderIds ?? [])
  const closedChapterIds = new Set(settings?.closedChapterIds ?? [])

  if (isLoading) return <p>Loading...</p>
  if (error || !folder) return <p>Not found, or you don't have access to it.</p>

  function handleCreateSubfolder(data: { name: string; description: string }) {
    createFolder.mutate(data, { onSuccess: () => setCreating(null) })
  }

  function handleCreateChapter(data: { name: string; description: string }) {
    createChapter.mutate(data, {
      onSuccess: (chapter) => {
        setCreating(null)
        navigate(`/chapters/${chapter.id}`)
      },
    })
  }

  function handleSaveSettings(data: { name: string; description: string; showBookColor: boolean }) {
    update.mutate(data, { onSuccess: () => setShowSettings(false) })
  }

  function confirmDelete() {
    const parentId = folder!.parentId
    del.mutate(folder!.id, {
      onSuccess: () => {
        // FolderPage doesn't unmount across this navigation (same route,
        // different :folderId), so confirmAction would otherwise carry over
        // and reopen this modal for whatever page we just landed on.
        setConfirmAction(null)
        navigate(parentId ? `/folders/${parentId}` : '/')
      },
    })
  }

  function confirmLeave() {
    if (!user) return
    leaveShare.mutate(
      { resourceType: 'folder', resourceId: folder!.id, userId: user.id },
      {
        onSuccess: () => {
          setConfirmAction(null)
          navigate('/')
        },
      },
    )
  }

  function toggleSubfolderOpen(folderId: string, isOpen: boolean) {
    const current = settings?.closedFolderIds ?? []
    updateSettings.mutate({
      closedFolderIds: isOpen ? [...current, folderId] : current.filter((id) => id !== folderId),
    })
  }

  function toggleChapterOpen(chapterId: string, isOpen: boolean) {
    const current = settings?.closedChapterIds ?? []
    updateSettings.mutate({
      closedChapterIds: isOpen ? [...current, chapterId] : current.filter((id) => id !== chapterId),
    })
  }

  const canEditSettings = isBook ? book?.role !== 'viewer' : folder.role !== 'viewer' || folder.directShare
  const canDelete = isBook ? book?.role === 'owner' : folder.role !== 'viewer'
  const hasClosedDescendants =
    !!treeIds &&
    (treeIds.folderIds.some((fid) => closedFolderIds.has(fid)) ||
      treeIds.chapterIds.some((cid) => closedChapterIds.has(cid)))

  const trailingMenuActions: MenuAction[] = [
    ...(hasClosedDescendants ? [{ label: 'Open all', onClick: () => openAll.mutate(folder.id) }] : []),
    ...(canDelete ? [{ label: 'Delete', onClick: () => setConfirmAction('delete'), danger: true }] : []),
  ]
  if (trailingMenuActions.length > 0) trailingMenuActions[0] = { ...trailingMenuActions[0], separatorBefore: true }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            {isBook
              ? 'Book'
              : folder.parentAccessible
                ? <Link to={`/folders/${folder.parentId}`}>&larr; Parent folder</Link>
                : 'Sub-folder'}
          </div>
          <h1>{folder.name}</h1>
          {folder.author && <p className="folder-author">by {folder.author}</p>}
          {folder.description && <p className="folder-description">{folder.description}</p>}
        </div>
        <div className="folder-page-actions" aria-label={`${isBook ? 'Book' : 'Sub-folder'} actions`}>
          <TreeItemMenu
            actions={[
              ...(canEditSettings
                ? [
                    {
                      label: 'Settings',
                      onClick: () => (isBook ? navigate(`/folders/${folder.id}/settings`) : setShowSettings(true)),
                    },
                  ]
                : []),
              { label: 'Stats', onClick: () => navigate(`/folders/${folder.id}/stats`) },
              { label: 'Goals', onClick: () => navigate(`/goals?resourceType=folder&resourceId=${folder.id}`) },
              {
                label: 'Download',
                submenu: [
                  { label: 'Download as .docx', onClick: () => triggerDownload(`/folders/${folder.id}/export.docx`) },
                  { label: 'Download as .rtf', onClick: () => triggerDownload(`/folders/${folder.id}/export.rtf`) },
                  { label: 'Download as .txt', onClick: () => triggerDownload(`/folders/${folder.id}/export.txt`) },
                  { label: 'Download as .md', onClick: () => triggerDownload(`/folders/${folder.id}/export.md`) },
                ],
              },
              ...trailingMenuActions,
            ]}
          />
        </div>
      </header>

      {showSettings && (
        <FolderSettingsModal
          folder={folder}
          saving={update.isPending}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
          onDelete={() => setConfirmAction('delete')}
          onLeave={folder.directShare ? () => setConfirmAction('leave') : undefined}
          canEdit={folder.role !== 'viewer'}
        />
      )}

      {confirmAction === 'delete' && (
        <ConfirmModal
          title={`Delete ${isBook ? 'book' : 'sub-folder'}`}
          message={`Delete this ${isBook ? 'book' : 'sub-folder'} "${folder.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          pending={del.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {confirmAction === 'leave' && (
        <ConfirmModal
          title={`Leave ${isBook ? 'book' : 'sub-folder'}`}
          message={`Leave this ${isBook ? 'book' : 'sub-folder'} "${folder.name}"? You'll lose access unless re-shared.`}
          confirmLabel="Leave"
          pending={leaveShare.isPending}
          onConfirm={confirmLeave}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {creating === 'folder' && (
        <CreateItemModal
          title="New sub-folder"
          nameLabel="Name"
          saving={createFolder.isPending}
          onClose={() => setCreating(null)}
          onCreate={handleCreateSubfolder}
        />
      )}

      {creating === 'chapter' && (
        <CreateItemModal
          title="New chapter"
          nameLabel="Name"
          saving={createChapter.isPending}
          onClose={() => setCreating(null)}
          onCreate={handleCreateChapter}
        />
      )}

      <section className="folder-section">
        <div className="folder-section-header">
          <div>
            <h2>Sub-folders</h2>
            <p>Keep related chapters together.</p>
          </div>
          <span className="folder-count">{folder.folders.length}</span>
        </div>
        {folder.folders.length > 0 ? (
          <ul className="folder-item-list sortable">
            {subfolderDrag.order.map((f, idx) => {
              const isOpen = !closedFolderIds.has(f.id)
              return (
                <li
                  key={f.id}
                  draggable
                  onDragStart={() => subfolderDrag.onDragStart(idx)}
                  onDragOver={(e) => subfolderDrag.onDragOver(idx, e)}
                  onDrop={subfolderDrag.onDrop}
                >
                  <span className="drag-handle" aria-hidden="true">⋮⋮</span>
                  <div className="folder-item-name">
                    {isOpen ? <Link to={`/folders/${f.id}`}>{f.name}</Link> : <span>{f.name}</span>}
                    {f.description && <p className="folder-item-description">{f.description}</p>}
                    {!isOpen && <small>Hidden from sidebar</small>}
                  </div>
                  <button type="button" className="item-visibility-button" onClick={() => toggleSubfolderOpen(f.id, isOpen)}>
                    {isOpen ? 'Close' : 'Open'}
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="folder-empty-state">No sub-folders yet.</p>
        )}
        {folder.role !== 'viewer' && (
          <button type="button" className="folder-action" onClick={() => setCreating('folder')}>Add sub-folder</button>
        )}
      </section>

      <section className="folder-section">
        <div className="folder-section-header">
          <div>
            <h2>Chapters</h2>
            <p>Drag chapters to change their order.</p>
          </div>
          <span className="folder-count">{folder.chapters.length}</span>
        </div>
        {folder.chapters.length > 0 ? (
          <ul className="folder-item-list sortable">
            {chapterDrag.order.map((c, idx) => {
              const isOpen = !closedChapterIds.has(c.id)
              return (
                <li
                  key={c.id}
                  draggable
                  onDragStart={() => chapterDrag.onDragStart(idx)}
                  onDragOver={(e) => chapterDrag.onDragOver(idx, e)}
                  onDrop={chapterDrag.onDrop}
                >
                  <span className="drag-handle" aria-hidden="true">⋮⋮</span>
                  <div className="folder-item-name">
                    {isOpen ? <Link to={`/chapters/${c.id}`}>{c.name}</Link> : <span>{c.name}</span>}
                    {c.description && <p className="folder-item-description">{c.description}</p>}
                    {!isOpen && <small>Hidden from sidebar</small>}
                  </div>
                  {folder.role !== 'viewer' && (
                    <button
                      type="button"
                      className={`item-visibility-button${c.completedAt !== null ? ' completed' : ''}`}
                      onClick={() =>
                        toggleComplete.mutate({ chapterId: c.id, folderId: folder.id, completed: c.completedAt === null })
                      }
                    >
                      {c.completedAt !== null ? '✓ Complete' : 'Mark complete'}
                    </button>
                  )}
                  <button type="button" className="item-visibility-button" onClick={() => toggleChapterOpen(c.id, isOpen)}>
                    {isOpen ? 'Close' : 'Open'}
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="folder-empty-state">No chapters yet.</p>
        )}
        {folder.role !== 'viewer' && (
          <button type="button" className="folder-action" onClick={() => setCreating('chapter')}>Add chapter</button>
        )}
      </section>
    </div>
  )
}
