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

/** P1.2 Book Types -- metadata/optional behavior layered on the existing
 * Book (root Folder), never a separate Journal/Novel/Documentation model.
 * Changing this only ever changes the stored value: never restructures,
 * renames, deletes, or migrates existing content, and is always
 * immediately reversible. */
export type BookType = 'general' | 'novel' | 'journal' | 'documentation'

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
  bookType: BookType
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
  /** P1.2: the Journal day this chapter represents, an ISO date
   * ("2026-08-29") or null for an ordinary chapter -- authoritative
   * regardless of this chapter's name, current folder, or Book Type. */
  journalDate: string | null
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

/** P1.1A -- stable format IDs only (shown in the UI as a rendered example,
 * never as this raw string -- see JOURNAL_DATE_FORMAT_OPTIONS). */
export type JournalDateFormat =
  | 'long_month_day_year'
  | 'short_month_day_year'
  | 'day_long_month_year'
  | 'day_short_month_year'
  | 'us_numeric'
  | 'day_first_numeric'
  | 'iso'
  | 'weekday_long'

export type JournalTimeFormat = '12_hour' | '24_hour'

export interface UserSettings {
  /** User-level default for newly generated Journal day-Chapter names --
   * for a shared Journal, the *Book owner's* value applies (see
   * JournalWriteTodayResult). Changing this never renames existing
   * Chapters. */
  journalDateFormat: JournalDateFormat
  /** User-level default for Write Today timestamp labels -- same
   * owner-authoritative rule as journalDateFormat. Changing this never
   * rewrites previously inserted timestamps. */
  journalTimeFormat: JournalTimeFormat
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

export type SearchScopeType = 'workspace' | 'book' | 'folder'
export type SearchMatchSource = 'title' | 'content' | 'notes'

export interface SearchSnippet {
  before: string
  /** Original matched text, casing preserved -- not the query as typed. */
  match: string
  after: string
  leadingEllipsis: boolean
  trailingEllipsis: boolean
}

export interface SearchMatch {
  chapterId: string
  chapterName: string
  bookId: string
  bookName: string
  bookColor: string | null
  source: SearchMatchSource
  /** Zero-based, independent per source -- null for a title match (a
   * chapter contributes at most one). Also doubles as the findIndex sent
   * to ChapterPage for jump-to-occurrence navigation. */
  occurrenceIndex: number | null
  /** Offsets into that source's canonical searchable plain-text form (see
   * services.html_to_search_text on the backend / canonicalSearchText on
   * the frontend) -- for a title match, into the title string itself. */
  startOffset: number
  endOffset: number
  snippet: SearchSnippet
}

export interface SearchResponse {
  query: string
  scopeType: SearchScopeType
  scopeId: string | null
  totalMatches: number
  totalChapters: number
  limit: number
  offset: number
  hasMore: boolean
  matches: SearchMatch[]
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
   * wordsPasted below. Kept alongside wordsWritten because WPM and goal
   * progress use this gross figure, never the net one. */
  wordsTyped: number
  /** All-time, personal count of words brought in via paste or an external
   * drop -- included in totalWords, but never in wordsTyped, goal
   * progress, or WPM. */
  wordsPasted: number
  /** All-time, personal count of genuinely typed/composed words removed --
   * see wordsWritten. */
  wordsDeleted: number
  /** The "Words written" stat shown in the UI: max(wordsTyped - wordsDeleted, 0). */
  wordsWritten: number
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
  /** Net "words written" (typed minus deleted, floored at 0), resource-wide
   * across every contributor -- not gross typed, and not personal-only. */
  recentVelocity7d: number
  recentVelocity30d: number
  /** WPM for the viewer only; never a collaborator blend. */
  wpm: number | null
}

export interface ActivityTotals {
  wordsTyped: number
  wordsPasted: number
  wordsDeleted: number
  /** max(wordsTyped - wordsDeleted, 0) -- the "Words written" stat. */
  wordsWritten: number
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

/** P1.2 "Write Today" -- POST /books/:id/journal/today's response. Hands
 * the frontend everything needed to navigate to the resolved Chapter and
 * append exactly one client-side timestamp (see ChapterEditor's
 * journalEntryRequest) without inserting it here. */
export interface JournalWriteTodayResult {
  chapter: ChapterSummary
  /** False when today's Chapter already existed and was simply reused. */
  created: boolean
  /** ISO date, the Book owner's local "today" -- see Chapter.journalDate. */
  journalDate: string
  /** Fresh per successful call -- consumed exactly once by the Chapter
   * page's timestamp-insertion handoff, so Strict Mode/rerenders/refetches
   * can never append a second timestamp for the same click. */
  entryRequestId: string
  /** ISO instant: when this Write Today request was made, not inserted
   * server-side. Kept for compatibility/diagnostics -- the frontend
   * inserts entryTimeLabel verbatim rather than reformatting this itself. */
  entryTimestamp: string
  /** P1.1A: entryTimestamp already formatted using the Book *owner's*
   * journalTimeFormat preference (e.g. "10:42 PM" or "22:42") -- insert
   * this exactly as returned. Guarantees every collaborator's client shows
   * the identical label regardless of their own browser locale/settings. */
  entryTimeLabel: string
  /** IANA zone, always the Book owner's (resolved, safely-falls-back-to-UTC)
   * timezone entryTimeLabel was formatted in. */
  journalTimezone: string
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
