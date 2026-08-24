import type { DragEvent } from 'react'

export const CHAPTER_DRAG_TYPE = 'application/x-calwriter-chapter'
export const FOLDER_DRAG_TYPE = 'application/x-calwriter-folder'

export interface ChapterDragPayload {
  chapterId: string
}

export interface FolderDragPayload {
  folderId: string
}

export function readChapterDragPayload(e: DragEvent): ChapterDragPayload | null {
  const raw = e.dataTransfer.getData(CHAPTER_DRAG_TYPE)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ChapterDragPayload
  } catch {
    return null
  }
}

export function readFolderDragPayload(e: DragEvent): FolderDragPayload | null {
  const raw = e.dataTransfer.getData(FOLDER_DRAG_TYPE)
  if (!raw) return null
  try {
    return JSON.parse(raw) as FolderDragPayload
  } catch {
    return null
  }
}

/** Vertical drop zone within a tree row: top third = insert as a sibling
 * before the target, bottom third = insert after, middle third = nest
 * inside the target (become its child) -- standard tree-UI convention. */
export type RowDropZone = 'before' | 'nest' | 'after'

export function rowDropZone(e: DragEvent<HTMLElement>): RowDropZone {
  const rect = e.currentTarget.getBoundingClientRect()
  const fraction = (e.clientY - rect.top) / rect.height
  if (fraction < 1 / 3) return 'before'
  if (fraction > 2 / 3) return 'after'
  return 'nest'
}
