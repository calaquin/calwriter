export type Role = 'owner' | 'editor' | 'viewer'

export interface Me {
  id: number
  username: string
  isAdmin: boolean
  csrfToken: string
  version: string
}

export interface Invite {
  token: string
  expiresAt: string
}

export interface Book {
  id: number
  name: string
  description: string
  author: string
  color: string
  role: Role
  createdAt: string
  updatedAt: string
}

export interface FolderSummary {
  id: number
  bookId: number
  parentId: number | null
  parentAccessible: boolean
  name: string
  description: string
  author: string
  color: string
  position: number
  role: Role
  /** A share exists on this exact folder for the current user (not an
   * ancestor's share, not ownership) -- distinct from `role`. */
  directShare: boolean
}

export interface ChapterSummary {
  id: number
  bookId: number
  folderId: number
  folderAccessible: boolean
  name: string
  description: string
  position: number
  updatedAt: string
  /** Set when the chapter's manual "Complete" toggle (Chapter Settings) is on. */
  completedAt: string | null
  role: Role
  directShare: boolean
}

export interface FolderDetail extends FolderSummary {
  folders: FolderSummary[]
  chapters: ChapterSummary[]
}

export interface ChapterDetail extends ChapterSummary {
  contentHtml: string
  notesText: string
}

export interface Share {
  userId: number
  username: string
  role: 'editor' | 'viewer'
}

export interface SharedItem {
  type: 'folder' | 'chapter'
  id: number
  parentId: number | null
  name: string
  role: Role
  bookName: string
}

export interface UserSettings {
  darkMode: boolean
  sidebarColor: string
  textColor: string
  bgColor: string
  toolbarColor: string
  editorColor: string
  darkSidebarColor: string
  darkTextColor: string
  darkBgColor: string
  darkToolbarColor: string
  darkEditorColor: string
  openBookIds: number[]
  closedFolderIds: number[]
  closedChapterIds: number[]
  bookOrder: number[]
  hiddenGoalIds: number[]
  goalOrder: number[]
}

export interface SearchResult extends ChapterSummary {
  matchType: 'chapter' | 'notes'
}

export interface Stats {
  totalWords: number
  wordsPerDay: Record<string, number>
}

export interface ChapterVersionSummary {
  id: number
  createdAt: string
  wordCount: number
  preview: string
}

export interface ChapterVersionDetail extends ChapterVersionSummary {
  contentHtml: string
}

export interface PresenceUser {
  userId: number
  username: string
}

export interface FolderTreeIds {
  folderIds: number[]
  chapterIds: number[]
}

export interface FolderTreeEntry {
  id: number
  type: 'folder' | 'chapter'
  name: string
  depth: number
}

export type GoalType = 'words' | 'chapters'
export type GoalCadence = 'daily' | 'weekly' | 'monthly'
export type GoalResourceType = 'folder' | 'chapter'

export interface Goal {
  id: number
  /** User-chosen label, e.g. "First draft push". Empty string if none was given. */
  name: string
  goalType: GoalType
  target: number
  /** Set for a recurring goal (its period auto-resets); null for a fixed date-range goal. */
  cadence: GoalCadence | null
  startDate: string
  /** Set for a fixed-range goal; null for a recurring one (open-ended). */
  endDate: string | null
  createdAt: string
  resourceType: GoalResourceType
  resourceId: number
  resourceName: string | null
  resourceIsBook: boolean | null
  /** Set only when the resource is a book itself (matches the sidebar's
   * own isBook-gated color usage) -- null for a sub-folder or chapter. */
  resourceColor: string | null
  /** Ancestor folders from the book root down to (not including) the
   * resource itself -- empty for a book, or anything sitting directly in
   * a book's root. Only the book entry has a color. */
  resourceBreadcrumb: { id: number; name: string; color: string | null }[]
  /** False if the underlying folder/chapter was unshared with you since -- the goal still shows, just flagged. */
  resourceAccessible: boolean
  current: number
  percent: number
  periodStart: string
  periodEnd: string | null
  achieved: boolean
  /** False only for a not-yet-started fixed-range word goal (startDate is in the future). */
  started: boolean
}

export interface GoalPeriodHistoryEntry {
  id: number
  periodStart: string
  periodEnd: string
  target: number
  current: number
  percent: number
  achieved: boolean
}

export interface GoalHistory {
  goal: Goal
  periods: GoalPeriodHistoryEntry[]
}
