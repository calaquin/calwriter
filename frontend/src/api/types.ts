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
  name: string
  description: string
  author: string
  color: string
  position: number
}

export interface ChapterSummary {
  id: number
  bookId: number
  folderId: number
  name: string
  description: string
  position: number
  updatedAt: string
}

export interface FolderDetail extends FolderSummary {
  folders: FolderSummary[]
  chapters: ChapterSummary[]
}

export interface ChapterDetail extends ChapterSummary {
  contentHtml: string
  notesText: string
}

export interface Collaborator {
  userId: number
  username: string
  role: 'editor' | 'viewer'
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
}

export interface SearchResult extends ChapterSummary {
  matchType: 'chapter' | 'notes'
}

export interface BookStats {
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
