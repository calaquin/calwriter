export type Role = 'owner' | 'editor' | 'viewer'

export interface Me {
  id: string
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
  id: string
  name: string
  description: string
  author: string
  color: string
  /** Whether this book's color may tint its chapters' editor backgrounds --
   * a sub-folder or chapter further down the tree can still opt out on its
   * own even when this is true. */
  showBookColor: boolean
  role: Role
  createdAt: string
  updatedAt: string
}

export interface FolderSummary {
  id: string
  bookId: string
  parentId: string | null
  parentAccessible: boolean
  name: string
  description: string
  author: string
  color: string
  /** Same opt-in/opt-out semantics as Book.showBookColor, scoped to this
   * sub-folder and everything nested under it. */
  showBookColor: boolean
  position: number
  role: Role
  /** A share exists on this exact folder for the current user (not an
   * ancestor's share, not ownership) -- distinct from `role`. */
  directShare: boolean
}

export interface ChapterSummary {
  id: string
  bookId: string
  folderId: string
  folderAccessible: boolean
  name: string
  description: string
  position: number
  updatedAt: string
  /** Set when the chapter's manual "Complete" toggle (Chapter Settings) is on. */
  completedAt: string | null
  /** This chapter's own opt-in/opt-out of the book-color background tint. */
  showBookColor: boolean
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
  /** The color the editor should actually tint its background with, already
   * resolved from the book's color and every showBookColor flag from the
   * book root down to this chapter -- null if any of them opted out, or the
   * book has no color set. */
  bookColor: string | null
}

export interface Share {
  userId: string
  username: string
  role: 'editor' | 'viewer'
}

export interface SharedItem {
  type: 'folder' | 'chapter'
  id: string
  parentId: string | null
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
  openBookIds: string[]
  closedFolderIds: string[]
  closedChapterIds: string[]
  bookOrder: string[]
  hiddenGoalIds: string[]
  goalOrder: string[]
  /** The one goal (if any) highlighted with a live progress bar in the
   * sidebar. At most one at a time -- setting this replaces whichever goal
   * held it before. */
  primaryGoalId: string | null
}

export interface SearchResult extends ChapterSummary {
  matchType: 'chapter' | 'notes'
}

export interface Stats {
  totalWords: number
  wordsPerDay: Record<string, number>
}

export interface WritingStreak {
  current: number
  longest: number
}

export interface GoalHitRate {
  achieved: number
  total: number
  /** null when the user has no elapsed goal periods yet -- distinct from a
   * real 0%, which would mean periods elapsed and none were achieved. */
  percent: number | null
}

export interface WeekOverWeekWords {
  thisWeek: number
  lastWeek: number
  /** null when lastWeek was 0 (e.g. a first active week) -- avoids a
   * divide-by-zero/fabricated infinity swing. */
  percentChange: number | null
}

export interface HeatmapBucket {
  /** 0 = Monday .. 6 = Sunday (Python's date.weekday() convention). */
  dayOfWeek: number
  hour: number
  activeSeconds: number
}

export interface BusiestResource {
  chapterId: string
  name: string
  activeSeconds: number
}

/** Workspace-scope stats: everything Stats has, plus the personal
 * (streak/heatmap/WPM/active-time) and resource-level (trend/busiest
 * resource) tiles that only make sense across the whole workspace. */
export interface WorkspaceStats extends Stats {
  streak: WritingStreak
  goalHitRate: GoalHitRate
  weekOverWeekWords: WeekOverWeekWords
  heatmap: HeatmapBucket[]
  busiestResource: BusiestResource | null
  avgWpm: number
  totalActiveSeconds: number
}

export interface StaleChapter {
  id: string
  name: string
  daysSinceActivity: number
}

export interface WordCountSpread {
  min: number
  max: number
  avg: number
}

export interface ChapterStatsBreakdown {
  id: string
  name: string
  versionCount: number
  recentVelocity7d: number
  recentVelocity30d: number
  wpm: number
}

/** Folder-scope stats: Stats plus the stale-chapters list, sibling
 * word-count spread, and a per-chapter breakdown table. */
export interface FolderStats extends Stats {
  staleChapters: StaleChapter[]
  /** null when the folder has no direct-child chapters to compare. */
  wordCountSpread: WordCountSpread | null
  chapters: ChapterStatsBreakdown[]
}

/** Chapter-scope stats: Stats plus that chapter's own WPM. */
export interface ChapterStats extends Stats {
  wpm: number
}

export interface ChapterVersionSummary {
  id: string
  createdAt: string
  wordCount: number
  preview: string
}

export interface ChapterVersionDetail extends ChapterVersionSummary {
  contentHtml: string
}

export interface PresenceUser {
  userId: string
  username: string
}

export interface FolderTreeIds {
  folderIds: string[]
  chapterIds: string[]
}

export interface FolderTreeEntry {
  id: string
  type: 'folder' | 'chapter'
  name: string
  depth: number
}

export type GoalType = 'words' | 'chapters'
export type GoalCadence = 'daily' | 'weekly' | 'monthly'
export type GoalResourceType = 'folder' | 'chapter'

export interface Goal {
  id: string
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
  resourceId: string
  resourceName: string | null
  resourceIsBook: boolean | null
  /** Set only when the resource is a book itself (matches the sidebar's
   * own isBook-gated color usage) -- null for a sub-folder or chapter. */
  resourceColor: string | null
  /** Ancestor folders from the book root down to (not including) the
   * resource itself -- empty for a book, or anything sitting directly in
   * a book's root. Only the book entry has a color. */
  resourceBreadcrumb: { id: string; name: string; color: string | null }[]
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
  id: string
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
