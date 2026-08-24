import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useFolder,
  useFolderTreeIds,
  useReorderFolderChildren,
  useMoveChapter,
  useMoveFolder,
  useUpdateFolder,
  useUpdateBook,
  useCreateFolder,
  useCreateChapter,
  useSettings,
  useUpdateSettings,
  useOpenAll,
} from '../api/hooks'
import { useTabs } from '../context/TabsContext'
import { triggerDownload } from '../api/client'
import TreeItemMenu, { type MenuAction } from './TreeItemMenu'
import CreateItemModal from './CreateItemModal'
import RenameModal from './RenameModal'
import ChapterTreeNode from './ChapterTreeNode'
import {
  CHAPTER_DRAG_TYPE,
  FOLDER_DRAG_TYPE,
  readChapterDragPayload,
  readFolderDragPayload,
  rowDropZone,
} from './chapterDrag'
import type { Role } from '../api/types'

export default function FolderTreeNode({
  folderId,
  name,
  level,
  parentId,
  role,
  color,
  closedFolderIds,
  closedChapterIds,
  isBook = level === 0,
  extraMenuActions,
}: {
  folderId: string
  name: string
  level: number
  parentId: string | null
  role: Role
  color?: string
  closedFolderIds: ReadonlySet<string>
  closedChapterIds: ReadonlySet<string>
  /** Defaults to `level === 0`. Pass explicitly for a folder rendered as a
   * top-level sidebar entry despite having a real (inaccessible) parent --
   * a sub-folder shared directly with the user, for instance -- so it's
   * still treated as an ordinary sub-folder rather than a book. */
  isBook?: boolean
  /** Extra rows appended to this node's own three-dot menu -- e.g. "Leave"
   * on a "Shared with me" sidebar entry. Not passed down to children. */
  extraMenuActions?: MenuAction[]
}) {
  const [expanded, setExpanded] = useState(level === 0)
  const [creating, setCreating] = useState<'folder' | 'chapter' | null>(null)
  const [renamingFolder, setRenamingFolder] = useState(false)
  const { data } = useFolder(expanded ? folderId : undefined)
  const { data: treeIds } = useFolderTreeIds(folderId)
  const hasChildren = data ? data.folders.length > 0 || data.chapters.length > 0 : true
  const canEdit = role !== 'viewer'
  const navigate = useNavigate()

  const reorder = useReorderFolderChildren(folderId)
  const moveChapter = useMoveChapter()
  const moveFolder = useMoveFolder()
  const updateFolder = useUpdateFolder(folderId, parentId)
  const updateBook = useUpdateBook(folderId)
  const createFolderMutation = useCreateFolder(folderId)
  const createChapterMutation = useCreateChapter(folderId)
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const openAll = useOpenAll()
  const { closeTabsForBook } = useTabs()

  function handleRenameFolder(nextName: string) {
    if (isBook) {
      updateBook.mutate({ name: nextName }, { onSuccess: () => setRenamingFolder(false) })
    } else {
      updateFolder.mutate({ name: nextName }, { onSuccess: () => setRenamingFolder(false) })
    }
  }

  function toggleFolderOpen() {
    if (isBook) {
      const current = settings?.openBookIds ?? []
      const isOpen = current.includes(folderId)
      updateSettings.mutate({ openBookIds: isOpen ? current.filter((id) => id !== folderId) : [...current, folderId] })
      if (isOpen) closeTabsForBook(folderId)
    } else {
      const current = settings?.closedFolderIds ?? []
      const isClosed = current.includes(folderId)
      updateSettings.mutate({
        closedFolderIds: isClosed ? current.filter((id) => id !== folderId) : [...current, folderId],
      })
    }
  }

  function handleCreateSubfolder(data: { name: string; description: string }) {
    createFolderMutation.mutate(data, {
      onSuccess: () => {
        setExpanded(true)
        setCreating(null)
      },
    })
  }

  function handleCreateChapter(data: { name: string; description: string }) {
    createChapterMutation.mutate(data, {
      onSuccess: (chapter) => {
        setExpanded(true)
        setCreating(null)
        navigate(`/chapters/${chapter.id}`)
      },
    })
  }

  function downloadFolder(ext: string) {
    triggerDownload(`/folders/${folderId}/export.${ext}`)
  }

  const [folderDragOver, setFolderDragOver] = useState<'nest' | null>(null)
  const [chapterDragOver, setChapterDragOver] = useState<{ id: string; zone: 'before' | 'nest' | 'after' } | null>(null)

  function handleChapterDragStart(chapterId: string, e: DragEvent) {
    e.dataTransfer.setData(CHAPTER_DRAG_TYPE, JSON.stringify({ chapterId }))
    e.dataTransfer.effectAllowed = 'move'
  }

  function handleChapterDragOver(chapterId: string, e: DragEvent<HTMLLIElement>) {
    if (!canEdit) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'move'
    const zone = rowDropZone(e)
    setChapterDragOver((prev) => (prev?.id === chapterId && prev.zone === zone ? prev : { id: chapterId, zone }))
  }

  // "nest" is handled entirely inside ChapterTreeNode itself (dropping a
  // chapter directly onto another chapter's own row = become its child, no
  // sibling-list knowledge needed) -- this only ever sees 'before'/'after',
  // reordering (or moving in as a new sibling) among this folder's own
  // direct chapters.
  function handleChapterSiblingDrop(targetChapterId: string, draggedChapterId: string, before: boolean) {
    if (!data) return
    if (draggedChapterId === targetChapterId) return
    const currentIds = data.chapters.map((c) => c.id).filter((id) => id !== draggedChapterId)
    const targetIndex = currentIds.indexOf(targetChapterId)
    const insertAt = targetIndex === -1 ? currentIds.length : before ? targetIndex : targetIndex + 1
    const newOrder = [...currentIds]
    newOrder.splice(insertAt, 0, draggedChapterId)
    const alreadyHere = data.chapters.some((c) => c.id === draggedChapterId)
    if (alreadyHere) {
      reorder.mutate({ type: 'chapter', order: newOrder })
    } else {
      moveChapter.mutate(
        { chapterId: draggedChapterId, folderId },
        { onSuccess: () => reorder.mutate({ type: 'chapter', order: newOrder }) },
      )
    }
  }

  function handleFolderRowDragOver(e: DragEvent) {
    if (!canEdit) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setFolderDragOver('nest')
  }

  function handleFolderRowDrop(e: DragEvent) {
    e.preventDefault()
    setFolderDragOver(null)
    if (!canEdit) return
    const chapterPayload = readChapterDragPayload(e)
    if (chapterPayload) {
      moveChapter.mutate({ chapterId: chapterPayload.chapterId, folderId })
      return
    }
    const folderPayload = readFolderDragPayload(e)
    if (folderPayload && folderPayload.folderId !== folderId) {
      moveFolder.mutate({ folderId: folderPayload.folderId, parentId: folderId })
    }
  }

  function handleFolderDragStart(e: DragEvent) {
    e.dataTransfer.setData(FOLDER_DRAG_TYPE, JSON.stringify({ folderId }))
    e.dataTransfer.effectAllowed = 'move'
    // Stops this drag from also being read as a drop target for itself via
    // bubbling into an ancestor FolderTreeNode's own row handlers.
    e.stopPropagation()
  }

  const folderIsOpen = isBook ? (settings?.openBookIds ?? []).includes(folderId) : !closedFolderIds.has(folderId)
  const downloadSubmenu = [
    { label: 'Download as .docx', onClick: () => downloadFolder('docx') },
    { label: 'Download as .rtf', onClick: () => downloadFolder('rtf') },
    { label: 'Download as .txt', onClick: () => downloadFolder('txt') },
    { label: 'Download as .md', onClick: () => downloadFolder('md') },
  ]
  const hasClosedDescendants =
    !!treeIds &&
    (treeIds.folderIds.some((fid) => closedFolderIds.has(fid)) || treeIds.chapterIds.some((cid) => closedChapterIds.has(cid)))
  const trailingMenuActions: MenuAction[] = [
    ...(hasClosedDescendants ? [{ label: 'Open all', onClick: () => openAll.mutate(folderId) }] : []),
    { label: folderIsOpen ? 'Close' : 'Open', onClick: toggleFolderOpen },
  ]
  trailingMenuActions[0] = { ...trailingMenuActions[0], separatorBefore: true }

  return (
    <li className={`tree-item collapsible${level === 0 ? ' book-root' : ''}${expanded ? '' : ' collapsed'}`}>
      <div
        className={`item-line${folderDragOver === 'nest' ? ' drag-over' : ''}`}
        // A book's own root folder can never be reparented (see
        // services.validate_folder_parent) -- not draggable, matching that.
        draggable={canEdit && !isBook}
        onDragStart={handleFolderDragStart}
        onDragOver={handleFolderRowDragOver}
        onDragLeave={() => setFolderDragOver(null)}
        onDrop={handleFolderRowDrop}
      >
        {hasChildren && (
          <span className="toggle" onClick={() => setExpanded((v) => !v)} role="button" tabIndex={0} />
        )}
        <Link to={`/folders/${folderId}`} style={isBook && color ? { color } : undefined}>
          {name}
        </Link>
        <TreeItemMenu
          actions={[
            ...(canEdit ? [{ label: 'Rename', onClick: () => setRenamingFolder(true) }] : []),
            ...(canEdit ? [{ label: 'New chapter', onClick: () => setCreating('chapter') }] : []),
            ...(canEdit ? [{ label: 'New folder', onClick: () => setCreating('folder') }] : []),
            ...(isBook
              ? canEdit
                ? [{ label: 'Settings', onClick: () => navigate(`/folders/${folderId}/settings`) }]
                : []
              : [{ label: 'Settings', onClick: () => navigate(`/folders/${folderId}?settings=1`) }]),
            { label: 'Stats', onClick: () => navigate(`/folders/${folderId}/stats`) },
            { label: 'Goals', onClick: () => navigate(`/goals?resourceType=folder&resourceId=${folderId}`) },
            { label: 'Download', submenu: downloadSubmenu },
            ...trailingMenuActions,
            ...(extraMenuActions ?? []),
          ]}
        />
      </div>
      {creating === 'folder' && (
        <CreateItemModal
          title="New folder"
          nameLabel="Name"
          saving={createFolderMutation.isPending}
          onClose={() => setCreating(null)}
          onCreate={handleCreateSubfolder}
        />
      )}
      {creating === 'chapter' && (
        <CreateItemModal
          title="New chapter"
          nameLabel="Name"
          saving={createChapterMutation.isPending}
          onClose={() => setCreating(null)}
          onCreate={handleCreateChapter}
        />
      )}
      {renamingFolder && (
        <RenameModal
          title={isBook ? 'Rename book' : 'Rename folder'}
          initialValue={name}
          saving={isBook ? updateBook.isPending : updateFolder.isPending}
          onClose={() => setRenamingFolder(false)}
          onSave={handleRenameFolder}
        />
      )}
      {expanded && data && (
        <ul>
          {data.folders.filter((f) => !closedFolderIds.has(f.id)).map((f) => (
            <FolderTreeNode
              key={f.id}
              folderId={f.id}
              name={f.name}
              level={level + 1}
              parentId={folderId}
              role={role}
              closedFolderIds={closedFolderIds}
              closedChapterIds={closedChapterIds}
            />
          ))}
          {data.chapters.filter((c) => !closedChapterIds.has(c.id)).map((c) => (
            <ChapterTreeNode
              key={c.id}
              chapterId={c.id}
              name={c.name}
              level={level + 1}
              role={role}
              closedChapterIds={closedChapterIds}
              hasChildren={c.hasChildren}
              draggable={canEdit}
              isDragOverZone={chapterDragOver?.id === c.id ? chapterDragOver.zone : null}
              onRowDragStart={(e) => handleChapterDragStart(c.id, e)}
              onRowDragOver={(e) => handleChapterDragOver(c.id, e)}
              onRowDragLeave={() => setChapterDragOver((prev) => (prev?.id === c.id ? null : prev))}
              onSiblingReorderDrop={(draggedId, before) => handleChapterSiblingDrop(c.id, draggedId, before)}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
