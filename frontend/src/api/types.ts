export type Role = 'owner' | 'editor' | 'viewer'

export interface Me {
  id: string
  username: string
  isAdmin: boolean
  /** IANA identifier; null only until first-login browser detection finishes. */
  timezone: string | null
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
  /** Exactly one of folderId/parentChapterId is ever set -- a chapter's
   * immediate parent is either a Folder or another Chapter, never both. */
  folderId: string | null
  folderAccessible: boolean
  /** Set instead of folderId when this chapter is nested inside another
   * chapter rather than sitting directly under a Folder. */
  parentChapterId: string | null
  parentChapterAccessible: boolean
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
  /** Whether this chapter has at least one child chapter -- drives whether
   * the sidebar tree shows an expand arrow for it at all, computed
   * server-side so the (common) case of a childless chapter never shows a
   * misleading arrow while still lazy-loading children only on expand. */
  hasChildren: boolean
}

export interface FolderDetail extends FolderSummary {
  folders: FolderSummary[]
  chapters: ChapterSummary[]
}

/** GET /chapters/:id/tree-children -- a chapter's own direct child chapters,
 * for the sidebar tree. Deliberately lighter than ChapterDetail (no
 * contentHtml/notesText) since expanding a tree node shouldn't pull a
 * chapter's full content along with it. */
export interface ChapterTreeChildren {
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

export type InternalReferenceTargetType = 'book' | 'folder' | 'chapter'

/** A permission-filtered row in the editor's CalWriter-item picker. Depth is
 * relative to the nearest readable root, so a narrow share never exposes the
 * names (or even the number) of inaccessible ancestors. */
export interface InternalReferenceTarget {
  targetType: InternalReferenceTargetType
  targetId: string
  name: string
  depth: number
  bookName: string
}

export interface InternalReferenceResolution {
  targetType: InternalReferenceTargetType
  targetId: string
  name: string
  route: string
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
  showWordCount: boolean
  showAverageWpm: boolean
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

/** Workspace-scope stats: document-state totals plus behavioral metrics
 * scoped exclusively to the current user. */
export interface WorkspaceStats extends Stats {
  chapterCount: number
  completedChapterCount: number
  revisionCount: number
  streak: WritingStreak
  goalHitRate: GoalHitRate
  weekOverWeekWords: WeekOverWeekWords
  heatmap: HeatmapBucket[]
  busiestResource: BusiestResource | null
  avgWpm: number | null
  totalActiveSeconds: number
  /** All-time, personal (this user only) genuinely-typed word count --
   * distinct from totalWords (the document's current size) and from
   * wordsPasted below. */
  wordsTyped: number
  /** All-time, personal count of words brought in via paste or an external
   * drop -- included in totalWords, but never in wordsTyped, goal
   * progress, or WPM. */
  wordsPasted: number
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
  /** WPM for the viewer only; never a collaborator blend. */
  wpm: number | null
}

export interface ActivityTotals {
  wordsTyped: number
  wordsPasted: number
  activeSeconds: number
}

export interface ContributorStats extends ActivityTotals {
  userId: string
  username: string
  /** Calculated from this contributor's words and active time only. */
  wpm: number | null
  isCurrentUser: boolean
}

export interface ResourceActivityStats {
  /** Additive totals across every historical contributor in this scope. */
  totals: ActivityTotals
  /** The current viewer's contribution, including a zero row if needed. */
  mine: ContributorStats
  /** Historical attribution; not filtered when a contributor is unshared. */
  contributors: ContributorStats[]
}

/** Folder-scope stats: Stats plus the stale-chapters list, sibling
 * word-count spread, and a per-chapter breakdown table. */
export interface FolderStats extends Stats {
  /** Recursive resource totals: all descendant folders and nested chapters. */
  chapterCount: number
  completedChapterCount: number
  revisionCount: number
  activity: ResourceActivityStats
  staleChapters: StaleChapter[]
  /** null when the folder has no direct-child chapters to compare. */
  wordCountSpread: WordCountSpread | null
  chapters: ChapterStatsBreakdown[]
}

/** Chapter-scope stats: document totals plus exact-chapter contributions. */
export interface ChapterStats extends Stats {
  activity: ResourceActivityStats
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

export interface ChapterHeartbeatResult {
  /** null until the user has recorded some active writing time here. */
  averageWpm: number | null
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
