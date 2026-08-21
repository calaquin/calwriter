import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useFolder,
  useReorderFolderChildren,
  useMoveChapter,
  useUpdateFolder,
  useUpdateBook,
  useRenameChapter,
  useSettings,
  useUpdateSettings,
} from '../api/hooks'
import { useTabs } from '../context/TabsContext'
import { triggerDownload } from '../api/client'
import TreeItemMenu from './TreeItemMenu'
import type { Role } from '../api/types'

const CHAPTER_DRAG_TYPE = 'application/x-calwriter-chapter'

interface ChapterDragPayload {
  chapterId: number
  sourceFolderId: number
}

function readChapterDragPayload(e: DragEvent): ChapterDragPayload | null {
  const raw = e.dataTransfer.getData(CHAPTER_DRAG_TYPE)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ChapterDragPayload
  } catch {
    return null
  }
}

export default function FolderTreeNode({
  folderId,
  name,
  level,
  parentId,
  role,
  color,
  closedFolderIds,
  closedChapterIds,
}: {
  folderId: number
  name: string
  level: number
  parentId: number | null
  role: Role
  color?: string
  closedFolderIds: ReadonlySet<number>
  closedChapterIds: ReadonlySet<number>
}) {
  const [expanded, setExpanded] = useState(level === 0)
  const { data } = useFolder(expanded ? folderId : undefined)
  const hasChildren = data ? data.folders.length > 0 || data.chapters.length > 0 : true
  const canEdit = role !== 'viewer'
  const isBook = level === 0
  const navigate = useNavigate()

  const reorder = useReorderFolderChildren(folderId)
  const moveChapter = useMoveChapter()
  const updateFolder = useUpdateFolder(folderId, parentId)
  const updateBook = useUpdateBook(folderId)
  const renameChapterMutation = useRenameChapter(folderId)
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const { closeTab, closeTabsForBook } = useTabs()

  function renameFolder() {
    const nextName = window.prompt(isBook ? 'Rename book' : 'Rename sub-folder', name)
    const trimmed = nextName?.trim()
    if (!trimmed || trimmed === name) return
    if (isBook) {
      updateBook.mutate({ name: trimmed })
    } else {
      updateFolder.mutate({ name: trimmed })
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

  function renameChapter(chapterId: number, chapterName: string) {
    const nextName = window.prompt('Rename chapter', chapterName)
    const trimmed = nextName?.trim()
    if (!trimmed || trimmed === chapterName) return
    renameChapterMutation.mutate({ chapterId, name: trimmed })
  }

  function toggleChapterOpen(chapterId: number) {
    const current = settings?.closedChapterIds ?? []
    const isClosed = current.includes(chapterId)
    updateSettings.mutate({
      closedChapterIds: isClosed ? current.filter((id) => id !== chapterId) : [...current, chapterId],
    })
    if (!isClosed) closeTab(chapterId)
  }

  function downloadFolder(ext: string) {
    triggerDownload(`/folders/${folderId}/export.${ext}`)
  }

  function downloadChapter(chapterId: number, ext: string) {
    triggerDownload(`/chapters/${chapterId}/export.${ext}`)
  }

  const [folderDragOver, setFolderDragOver] = useState(false)
  const [chapterDragOver, setChapterDragOver] = useState<{ id: number; before: boolean } | null>(null)

  function handleChapterDragStart(chapterId: number, e: DragEvent) {
    const payload: ChapterDragPayload = { chapterId, sourceFolderId: folderId }
    e.dataTransfer.setData(CHAPTER_DRAG_TYPE, JSON.stringify(payload))
    e.dataTransfer.effectAllowed = 'move'
  }

  function handleChapterDragOver(chapterId: number, e: DragEvent<HTMLLIElement>) {
    if (!canEdit) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'move'
    const rect = e.currentTarget.getBoundingClientRect()
    const before = e.clientY < rect.top + rect.height / 2
    setChapterDragOver((prev) => (prev?.id === chapterId && prev.before === before ? prev : { id: chapterId, before }))
  }

  function handleChapterDrop(targetChapterId: number, e: DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    const dropBefore = chapterDragOver?.id === targetChapterId ? chapterDragOver.before : true
    setChapterDragOver(null)
    setFolderDragOver(false)
    if (!canEdit || !data) return
    const payload = readChapterDragPayload(e)
    if (!payload) return
    const { chapterId, sourceFolderId } = payload
    if (sourceFolderId === folderId && chapterId === targetChapterId) return

    const currentIds = data.chapters.map((c) => c.id).filter((id) => id !== chapterId)
    const targetIndex = currentIds.indexOf(targetChapterId)
    const insertAt = targetIndex === -1 ? currentIds.length : dropBefore ? targetIndex : targetIndex + 1
    const newOrder = [...currentIds]
    newOrder.splice(insertAt, 0, chapterId)

    if (sourceFolderId === folderId) {
      reorder.mutate({ type: 'chapter', order: newOrder })
    } else {
      moveChapter.mutate(
        { chapterId, sourceFolderId, folderId },
        { onSuccess: () => reorder.mutate({ type: 'chapter', order: newOrder }) },
      )
    }
  }

  function handleFolderRowDragOver(e: DragEvent) {
    if (!canEdit) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setFolderDragOver(true)
  }

  function handleFolderRowDrop(e: DragEvent) {
    e.preventDefault()
    setFolderDragOver(false)
    if (!canEdit) return
    const payload = readChapterDragPayload(e)
    if (!payload || payload.sourceFolderId === folderId) return
    moveChapter.mutate({ chapterId: payload.chapterId, sourceFolderId: payload.sourceFolderId, folderId })
  }

  const folderIsOpen = isBook ? (settings?.openBookIds ?? []).includes(folderId) : !closedFolderIds.has(folderId)
  const downloadSubmenu = (kind: 'folder' | number) => [
    { label: 'Download as .docx', onClick: () => (kind === 'folder' ? downloadFolder('docx') : downloadChapter(kind, 'docx')) },
    { label: 'Download as .rtf', onClick: () => (kind === 'folder' ? downloadFolder('rtf') : downloadChapter(kind, 'rtf')) },
    { label: 'Download as .txt', onClick: () => (kind === 'folder' ? downloadFolder('txt') : downloadChapter(kind, 'txt')) },
    { label: 'Download as .md', onClick: () => (kind === 'folder' ? downloadFolder('md') : downloadChapter(kind, 'md')) },
  ]

  return (
    <li className={`tree-item collapsible${level === 0 ? ' book-root' : ''}${expanded ? '' : ' collapsed'}`}>
      <div
        className={`item-line${folderDragOver ? ' drag-over' : ''}`}
        onDragOver={handleFolderRowDragOver}
        onDragLeave={() => setFolderDragOver(false)}
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
            ...(canEdit ? [{ label: 'Rename', onClick: renameFolder }] : []),
            ...(isBook
              ? canEdit
                ? [{ label: 'Settings', onClick: () => navigate(`/folders/${folderId}/settings`) }]
                : []
              : [{ label: 'Settings', onClick: () => navigate(`/folders/${folderId}?settings=1`) }]),
            { label: 'Download', submenu: downloadSubmenu('folder') },
            { label: folderIsOpen ? 'Close' : 'Open', onClick: toggleFolderOpen, separatorBefore: true },
          ]}
        />
      </div>
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
            <li
              key={c.id}
              className={`tree-item chapter-item${
                chapterDragOver?.id === c.id ? (chapterDragOver.before ? ' drag-over-top' : ' drag-over-bottom') : ''
              }`}
              draggable={canEdit}
              onDragStart={(e) => handleChapterDragStart(c.id, e)}
              onDragOver={(e) => handleChapterDragOver(c.id, e)}
              onDragLeave={() => setChapterDragOver((prev) => (prev?.id === c.id ? null : prev))}
              onDrop={(e) => handleChapterDrop(c.id, e)}
            >
              <Link to={`/chapters/${c.id}`}>{c.name}</Link>
              <TreeItemMenu
                actions={[
                  ...(canEdit ? [{ label: 'Rename', onClick: () => renameChapter(c.id, c.name) }] : []),
                  { label: 'Settings', onClick: () => navigate(`/chapters/${c.id}?settings=1`) },
                  { label: 'Download', submenu: downloadSubmenu(c.id) },
                  {
                    label: closedChapterIds.has(c.id) ? 'Open' : 'Close',
                    onClick: () => toggleChapterOpen(c.id),
                    separatorBefore: true,
                  },
                ]}
              />
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
