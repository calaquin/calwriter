import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useChapterTreeChildren,
  useReorderChapterChildren,
  useMoveChapter,
  useRenameChapter,
  useCreateNestedChapter,
  useSettings,
  useUpdateSettings,
} from '../api/hooks'
import { useTabs } from '../context/TabsContext'
import { triggerDownload } from '../api/client'
import TreeItemMenu from './TreeItemMenu'
import CreateItemModal from './CreateItemModal'
import RenameModal from './RenameModal'
import { CHAPTER_DRAG_TYPE, readChapterDragPayload, rowDropZone } from './chapterDrag'
import type { Role } from '../api/types'

/** A chapter row in the sidebar tree that can itself recurse into nested
 * child chapters -- the recursive counterpart to FolderTreeNode, for a
 * chapter with its own children (see P0.3). Renders both as a leaf a
 * parent list can reorder (drag/drop props below, owned by whichever
 * FolderTreeNode or ChapterTreeNode renders this list) and as a container
 * that owns reorder state for its OWN children. */
export default function ChapterTreeNode({
  chapterId,
  name,
  level,
  role,
  closedChapterIds,
  hasChildren,
  draggable,
  isDragOverZone,
  onRowDragStart,
  onRowDragOver,
  onRowDragLeave,
  onSiblingReorderDrop,
}: {
  chapterId: string
  name: string
  level: number
  role: Role
  closedChapterIds: ReadonlySet<string>
  /** From ChapterSummary.hasChildren -- server-computed, so a childless
   * chapter (the common case) never shows a misleading expand arrow. */
  hasChildren: boolean
  /** Whether this row can be dragged -- false when the current user can't edit. */
  draggable: boolean
  /** Set by whichever parent owns this row's sibling list, when a drag is
   * currently hovering over this exact row. */
  isDragOverZone: 'before' | 'nest' | 'after' | null
  onRowDragStart: (e: DragEvent) => void
  onRowDragOver: (e: DragEvent<HTMLLIElement>) => void
  onRowDragLeave: () => void
  /** Called only for a 'before'/'after' drop -- nesting (a 'nest' drop) is
   * handled entirely inside this component, since it never needs the
   * sibling list. */
  onSiblingReorderDrop: (draggedChapterId: string, before: boolean) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [creating, setCreating] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const canEdit = role !== 'viewer'
  const navigate = useNavigate()
  const { closeTab } = useTabs()

  // Fetched whenever expanded, not gated on `hasChildren` too -- creating
  // this chapter's first-ever child force-expands it (see
  // handleCreateNested) before the `hasChildren` prop (owned by whichever
  // list rendered this row) has had a chance to catch up via its own
  // refetch, so gating the fetch on that stale value would show an empty
  // list right after creating the very child it should display.
  const { data } = useChapterTreeChildren(expanded ? chapterId : undefined)

  const reorder = useReorderChapterChildren(chapterId)
  const moveChapter = useMoveChapter()
  const renameMutation = useRenameChapter()
  const createNestedMutation = useCreateNestedChapter(chapterId)
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()

  const [ownDragOver, setOwnDragOver] = useState<{ id: string; zone: 'before' | 'nest' | 'after' } | null>(null)

  function handleCreateNested(data: { name: string; description: string }) {
    createNestedMutation.mutate(data, {
      onSuccess: (chapter) => {
        setExpanded(true)
        setCreating(false)
        navigate(`/chapters/${chapter.id}`)
      },
    })
  }

  function handleRename(nextName: string) {
    renameMutation.mutate({ chapterId, name: nextName }, { onSuccess: () => setRenaming(false) })
  }

  function toggleOpen() {
    const current = settings?.closedChapterIds ?? []
    const isClosed = current.includes(chapterId)
    updateSettings.mutate({
      closedChapterIds: isClosed ? current.filter((id) => id !== chapterId) : [...current, chapterId],
    })
    if (!isClosed) closeTab(chapterId)
  }

  function downloadChapter(ext: string) {
    triggerDownload(`/chapters/${chapterId}/export.${ext}`)
  }

  // Drag/drop for THIS node's own children -- mirrors FolderTreeNode's
  // chapter handling exactly, just scoped to a parent chapter instead of a
  // parent folder.
  function handleChildDragStart(childId: string, e: DragEvent) {
    e.dataTransfer.setData(CHAPTER_DRAG_TYPE, JSON.stringify({ chapterId: childId }))
    e.dataTransfer.effectAllowed = 'move'
    e.stopPropagation()
  }

  function handleChildDragOver(childId: string, e: DragEvent<HTMLLIElement>) {
    if (!canEdit) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'move'
    const zone = rowDropZone(e)
    setOwnDragOver((prev) => (prev?.id === childId && prev.zone === zone ? prev : { id: childId, zone }))
  }

  function handleChildSiblingDrop(targetChapterId: string, draggedChapterId: string, before: boolean) {
    if (!data) return
    if (draggedChapterId === targetChapterId) return
    const currentIds = data.chapters.map((c) => c.id).filter((cid) => cid !== draggedChapterId)
    const targetIndex = currentIds.indexOf(targetChapterId)
    const insertAt = targetIndex === -1 ? currentIds.length : before ? targetIndex : targetIndex + 1
    const newOrder = [...currentIds]
    newOrder.splice(insertAt, 0, draggedChapterId)
    const alreadyHere = data.chapters.some((c) => c.id === draggedChapterId)
    if (alreadyHere) {
      reorder.mutate(newOrder)
    } else {
      moveChapter.mutate({ chapterId: draggedChapterId, parentChapterId: chapterId }, { onSuccess: () => reorder.mutate(newOrder) })
    }
  }

  // This node's OWN row as a drop target -- "nest" always means "become my
  // child" (self-contained, no sibling-list knowledge needed); "before"/
  // "after" delegates to whichever parent owns this row's own sibling list.
  function handleOwnRowDrop(e: DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    const zone = isDragOverZone
    onRowDragLeave()
    if (!canEdit) return
    const payload = readChapterDragPayload(e)
    if (!payload || payload.chapterId === chapterId) return
    if (zone === 'nest') {
      moveChapter.mutate({ chapterId: payload.chapterId, parentChapterId: chapterId })
      setExpanded(true)
    } else {
      onSiblingReorderDrop(payload.chapterId, zone !== 'after')
    }
  }

  const downloadSubmenu = [
    { label: 'Download as .docx', onClick: () => downloadChapter('docx') },
    { label: 'Download as .rtf', onClick: () => downloadChapter('rtf') },
    { label: 'Download as .txt', onClick: () => downloadChapter('txt') },
    { label: 'Download as .md', onClick: () => downloadChapter('md') },
  ]

  return (
    <li
      // Deliberately NOT the `chapter-item` class here -- that's a flat-leaf
      // style (display:flex directly on the <li>, no nested <ul> support)
      // still correctly used by Sidebar.tsx's non-collapsible "shared with
      // me" chapter rows. This <li> can now contain a nested <ul> of its
      // own children (see below), so it needs the same collapsible-container
      // shape as FolderTreeNode's <li> -- `chapter-node` carries only the
      // drag-affordance styling that's still chapter-specific.
      className={`tree-item chapter-node collapsible${expanded ? '' : ' collapsed'}${
        isDragOverZone === 'before' ? ' drag-over-top' : isDragOverZone === 'after' ? ' drag-over-bottom' : ''
      }`}
      draggable={draggable}
      onDragStart={onRowDragStart}
      onDragOver={onRowDragOver}
      onDragLeave={onRowDragLeave}
      onDrop={handleOwnRowDrop}
    >
      <div className={`item-line${isDragOverZone === 'nest' ? ' drag-over' : ''}`}>
        {hasChildren && <span className="toggle" onClick={() => setExpanded((v) => !v)} role="button" tabIndex={0} />}
        <Link to={`/chapters/${chapterId}`}>{name}</Link>
        <TreeItemMenu
          actions={[
            ...(canEdit ? [{ label: 'Rename', onClick: () => setRenaming(true) }] : []),
            ...(canEdit ? [{ label: 'New sub-chapter', onClick: () => setCreating(true) }] : []),
            { label: 'Settings', onClick: () => navigate(`/chapters/${chapterId}?settings=1`) },
            { label: 'Stats', onClick: () => navigate(`/chapters/${chapterId}/stats`) },
            { label: 'Goals', onClick: () => navigate(`/goals?resourceType=chapter&resourceId=${chapterId}`) },
            { label: 'Download', submenu: downloadSubmenu },
            {
              label: closedChapterIds.has(chapterId) ? 'Open' : 'Close',
              onClick: toggleOpen,
              separatorBefore: true,
            },
          ]}
        />
      </div>
      {creating && (
        <CreateItemModal
          title="New sub-chapter"
          nameLabel="Name"
          saving={createNestedMutation.isPending}
          onClose={() => setCreating(false)}
          onCreate={handleCreateNested}
        />
      )}
      {renaming && (
        <RenameModal
          title="Rename chapter"
          initialValue={name}
          saving={renameMutation.isPending}
          onClose={() => setRenaming(false)}
          onSave={handleRename}
        />
      )}
      {expanded && data && (
        <ul>
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
              isDragOverZone={ownDragOver?.id === c.id ? ownDragOver.zone : null}
              onRowDragStart={(e) => handleChildDragStart(c.id, e)}
              onRowDragOver={(e) => handleChildDragOver(c.id, e)}
              onRowDragLeave={() => setOwnDragOver((prev) => (prev?.id === c.id ? null : prev))}
              onSiblingReorderDrop={(draggedId, before) => handleChildSiblingDrop(c.id, draggedId, before)}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
