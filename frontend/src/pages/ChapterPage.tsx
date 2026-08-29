import { useEffect, useRef, useState } from 'react'
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useChapter,
  useUpdateChapter,
  useDeleteChapter,
  useChapterPresence,
  useChapterPresenceHeartbeat,
  useChapterTreeChildren,
  useLeaveShare,
  useSettings,
} from '../api/hooks'
import { ApiError } from '../api/client'
import { useDebouncedCallback } from '../hooks/useDebouncedCallback'
import { useBodyClass } from '../hooks/useBodyClass'
import { useTabs, tabBackTarget } from '../context/TabsContext'
import { useAuth } from '../context/AuthContext'
import { useSidebarVisibility } from '../context/SidebarVisibilityContext'
import { findLiteralOccurrences } from '../utils/searchText'
import ChapterEditor from '../components/ChapterEditor'
import ChapterTabs from '../components/ChapterTabs'
import ChapterSettingsModal from '../components/ChapterSettingsModal'
import ChapterHistoryModal from '../components/ChapterHistoryModal'
import ConfirmModal from '../components/ConfirmModal'
import { copyText } from '../utils/clipboard'

const STALE_SEARCH_MATCH_MESSAGE = 'Search match is no longer present.'

const NOTES_COLLAPSED_KEY = 'calwriter:notesCollapsed'
const WRITE_MODE_KEY = 'calwriter:writeMode'
const SUBCHAPTERS_PANEL_HEIGHT_KEY = 'calwriter:subChaptersPanelHeight'
const PRESENCE_HEARTBEAT_MS = 20000
// Floors for the notes-editor/sub-chapters-panel split -- keep both regions
// usable even after a drag or a viewport resize leaves little room to work with.
const MIN_NOTES_HEIGHT = 80
const MIN_SUBCHAPTERS_PANEL_HEIGHT = 60

function isConflict(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409
}

export default function ChapterPage() {
  const { chapterId } = useParams()
  const id = chapterId
  const { data: chapter, isLoading, error } = useChapter(id)
  const { data: settings } = useSettings()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const qc = useQueryClient()
  useBodyClass('chapter-view')
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [confirmAction, setConfirmAction] = useState<'delete' | 'leave' | null>(null)

  useEffect(() => {
    if (searchParams.get('settings') !== '1') return
    setShowSettings(true)
    const next = new URLSearchParams(searchParams)
    next.delete('settings')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // Search 2.0 (P1.1) jump-to-occurrence handoff -- see the Search page's
  // matchHref. `find`/`findSource`/`findIndex` are a temporary navigation
  // handoff, not durable chapter state: cleared from the URL (via history
  // replace, so Back still returns to the Search results, not to this
  // intermediate state) once handled, successfully or not.
  const findQuery = searchParams.get('find')
  const findSource = searchParams.get('findSource')
  const findIndex = Number(searchParams.get('findIndex') ?? '0') || 0
  const findRequest = findQuery && findSource === 'content' ? { query: findQuery, occurrenceIndex: findIndex } : null
  const [staleSearchMatch, setStaleSearchMatch] = useState(false)

  function clearFindParams() {
    const next = new URLSearchParams(searchParams)
    next.delete('find')
    next.delete('findSource')
    next.delete('findIndex')
    setSearchParams(next, { replace: true })
  }

  function handleContentFindHandled(found: boolean) {
    if (!found) setStaleSearchMatch(true)
    clearFindParams()
  }

  // P1.2/P1.1A Journal "Write Today" timestamp handoff -- see FolderPage's
  // handleWriteToday. journalEntry/journalEntryTimeLabel are their own
  // separate temporary params (never find/findSource/findIndex) so Journal
  // and Search 2.0 navigation can never interfere with one another, even
  // if a link somehow carried both. journalEntryTimeLabel arrives already
  // formatted with the Book owner's journalTimeFormat preference (see
  // JournalWriteTodayResult) -- inserted verbatim, never reformatted here.
  // Cleared the same history-replace way once ChapterEditor confirms the
  // timestamp was applied.
  const journalEntryId = searchParams.get('journalEntry')
  const journalEntryTimeLabel = searchParams.get('journalEntryTimeLabel')
  const journalEntryRequest =
    journalEntryId && journalEntryTimeLabel
      ? { requestId: journalEntryId, timeLabel: journalEntryTimeLabel }
      : null

  function handleJournalEntryHandled() {
    const next = new URLSearchParams(searchParams)
    next.delete('journalEntry')
    next.delete('journalEntryTimeLabel')
    setSearchParams(next, { replace: true })
  }

  const [editorResetKey, setEditorResetKey] = useState(0)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved')
  const [hasConflict, setHasConflict] = useState(false)
  const [wordCount, setWordCount] = useState(0)
  const [averageWpm, setAverageWpm] = useState<number | null>(null)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const [notesCopyStatus, setNotesCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const pendingContentRef = useRef('')
  const notesRef = useRef<HTMLTextAreaElement>(null)
  // Mirrors of wordCount/writing-activity for the heartbeat interval below.
  // That interval is deliberately created once per chapter (deps: [id], see
  // its own comment) so it never sees fresh state through closure -- refs,
  // updated on every word-count/content change, are what let each 20s tick
  // report live values instead of whatever they were when the interval was
  // created.
  const wordCountRef = useRef(0)
  // Cumulative *since this chapter was opened* typed/pasted/deleted word totals --
  // deliberately never reset by a successful heartbeat (only by opening a
  // different chapter, i.e. the interval effect re-running below). The
  // server diffs these against its own last-recorded totals the same way
  // it already does for wordCountRef, which is what makes the transport
  // self-healing: a dropped heartbeat's words are caught up by the next
  // one instead of lost, and a duplicated heartbeat can't double-credit.
  const typedWordsTotalRef = useRef(0)
  const pastedWordsTotalRef = useRef(0)
  const deletedWordsTotalRef = useRef(0)
  // Unlike the two totals above, this one *is* reset after each heartbeat
  // send -- it's a lower-stakes "did genuine typing/deleting input happen
  // this interval" boolean gating active-writing-seconds, not a word count,
  // so losing one interval's worth on a dropped request is an acceptable
  // (and pre-existing-shape) risk.
  const hadTypingSinceHeartbeatRef = useRef(false)

  const hasUnsavedChanges = saveStatus !== 'saved'
  const blocker = useBlocker(hasUnsavedChanges)

  useEffect(() => {
    if (!hasUnsavedChanges) return
    function warnBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [hasUnsavedChanges])

  useEffect(() => {
    if (blocker.state !== 'blocked') setCopyStatus('idle')
  }, [blocker.state])

  async function copyChapterText() {
    const text = document.getElementById('chapter_editor')?.innerText ?? ''
    setCopyStatus((await copyText(text)) ? 'copied' : 'error')
  }

  async function copyNotesText() {
    const text = notesRef.current?.value ?? ''
    setNotesCopyStatus((await copyText(text)) ? 'copied' : 'error')
    setTimeout(() => setNotesCopyStatus('idle'), 2000)
  }

  const heartbeat = useChapterPresenceHeartbeat(id)
  const { data: presentUsers } = useChapterPresence(id)
  const { data: subChapters } = useChapterTreeChildren(chapter?.hasChildren ? chapter.id : undefined)

  useEffect(() => {
    if (!id) return
    // New chapter, new editing session -- the cumulative totals restart at
    // 0 (the server-side diff self-corrects against its own last-recorded
    // values regardless, but starting clean here matches ChapterEditor
    // resetting its own mirrors on the same chapter-switch boundary).
    typedWordsTotalRef.current = 0
    pastedWordsTotalRef.current = 0
    deletedWordsTotalRef.current = 0
    hadTypingSinceHeartbeatRef.current = false
    setAverageWpm(null)
    function fireHeartbeat() {
      heartbeat.mutate({
        wordCount: wordCountRef.current,
        typedWordsTotal: typedWordsTotalRef.current,
        pastedWordsTotal: pastedWordsTotalRef.current,
        deletedWordsTotal: deletedWordsTotalRef.current,
        hadTypingInput: hadTypingSinceHeartbeatRef.current,
      }, {
        onSuccess: (result) => setAverageWpm(result.averageWpm),
      })
      hadTypingSinceHeartbeatRef.current = false
    }
    fireHeartbeat()
    const interval = setInterval(fireHeartbeat, PRESENCE_HEARTBEAT_MS)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const [notesCollapsed, setNotesCollapsed] = useState(() => {
    try {
      const stored = localStorage.getItem(NOTES_COLLAPSED_KEY)
      if (stored !== null) return stored === 'true'
      return window.matchMedia('(max-width: 900px)').matches
    } catch {
      return false
    }
  })

  function toggleNotesCollapsed() {
    setNotesCollapsed((collapsed) => {
      const next = !collapsed
      try {
        localStorage.setItem(NOTES_COLLAPSED_KEY, String(next))
      } catch {
        // ignore -- collapsed state just won't persist across reloads
      }
      return next
    })
  }

  // Search 2.0: a Notes-source jump-to-occurrence result needs the panel
  // visibly expanded -- forced open WITHOUT going through
  // toggleNotesCollapsed (i.e. never persisted to NOTES_COLLAPSED_KEY), so
  // Search temporarily borrowing the panel doesn't overwrite the user's own
  // collapsed/expanded preference. They can still collapse/expand normally
  // afterward.
  useEffect(() => {
    if (findSource === 'notes' && findQuery) setNotesCollapsed(false)
  }, [findSource, findQuery])

  useEffect(() => {
    if (findSource !== 'notes' || !findQuery || notesCollapsed) return
    const textarea = notesRef.current
    // The chapter (and this effect, since hooks run before ChapterPage's own
    // own `if (isLoading) return <p>Loading...</p>`) can mount before the
    // Notes textarea itself does -- chapter?.id in the deps below re-fires
    // this once loading finishes and the ref is actually attached, instead
    // of silently no-op'ing forever on a null ref from that first pass.
    if (!textarea) return
    // Searches the *live* textarea value (not the possibly-stale chapter.notesText
    // from the last fetch) -- same "trust current content over whatever was
    // true when the user searched" approach as ChapterEditor's own findRequest.
    const occurrences = findLiteralOccurrences(textarea.value, findQuery)
    const span = occurrences[findIndex]
    if (!span) {
      setStaleSearchMatch(true)
      clearFindParams()
      return
    }
    textarea.focus()
    textarea.setSelectionRange(span[0], span[1])
    clearFindParams()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findSource, findQuery, findIndex, notesCollapsed, chapter?.id])

  useEffect(() => {
    if (!staleSearchMatch) return
    const timer = setTimeout(() => setStaleSearchMatch(false), 6000)
    return () => clearTimeout(timer)
  }, [staleSearchMatch])

  // The user-dragged height of the sub-chapters panel, in px -- null means
  // "no override yet", i.e. fall back to the CSS default (natural content
  // height, capped at 50% of the notes/sub-chapters split area). A global
  // preference like notesCollapsed/writeMode above, not per-chapter: it's a
  // "how much room do I like for this kind of panel" setting, not something
  // tied to any one chapter's content.
  const [subChaptersPanelHeight, setSubChaptersPanelHeight] = useState<number | null>(() => {
    try {
      const stored = localStorage.getItem(SUBCHAPTERS_PANEL_HEIGHT_KEY)
      return stored !== null ? Number(stored) : null
    } catch {
      return null
    }
  })
  const notesSplitRef = useRef<HTMLDivElement>(null)
  // Mirrors subChaptersPanelHeight during a drag so pointer-up can persist
  // the latest value without racing the setState/re-render cycle.
  const subChaptersPanelHeightRef = useRef(subChaptersPanelHeight)
  const resizeDragRef = useRef<{ pointerId: number; startY: number; startHeight: number } | null>(null)

  function handleResizerPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const panelEl = notesSplitRef.current?.querySelector<HTMLElement>('.sub-chapters-panel')
    if (!panelEl) return
    resizeDragRef.current = { pointerId: e.pointerId, startY: e.clientY, startHeight: panelEl.getBoundingClientRect().height }
    e.currentTarget.setPointerCapture(e.pointerId)
    document.body.style.userSelect = 'none'
  }

  function handleResizerPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const drag = resizeDragRef.current
    const splitEl = notesSplitRef.current
    if (!drag || !splitEl) return
    const availableHeight = splitEl.getBoundingClientRect().height
    const maxPanelHeight = Math.max(MIN_SUBCHAPTERS_PANEL_HEIGHT, availableHeight - MIN_NOTES_HEIGHT)
    // Dragging the handle up (cursor Y decreases) grows the panel below it.
    const delta = drag.startY - e.clientY
    const next = Math.min(maxPanelHeight, Math.max(MIN_SUBCHAPTERS_PANEL_HEIGHT, drag.startHeight + delta))
    subChaptersPanelHeightRef.current = next
    setSubChaptersPanelHeight(next)
  }

  function handleResizerPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    if (!resizeDragRef.current) return
    resizeDragRef.current = null
    e.currentTarget.releasePointerCapture(e.pointerId)
    document.body.style.userSelect = ''
    try {
      if (subChaptersPanelHeightRef.current !== null) {
        localStorage.setItem(SUBCHAPTERS_PANEL_HEIGHT_KEY, String(subChaptersPanelHeightRef.current))
      }
    } catch {
      // ignore -- the chosen height just won't persist across reloads
    }
  }

  const [writeMode, setWriteMode] = useState(() => {
    try {
      return localStorage.getItem(WRITE_MODE_KEY) === 'true'
    } catch {
      return false
    }
  })
  const { sidebarHidden, toggleSidebar } = useSidebarVisibility()

  // Write Mode is a single on/off unit: entering it always ends with the app
  // sidebar hidden (regardless of whatever it was before), leaving it always
  // ends with the sidebar shown again -- rather than reusing sidebarHidden's
  // own persisted preference directly, which would also affect it outside
  // the editor (e.g. the sidebar's own collapse arrow, or the mobile default).
  // toggleSidebar() is called here directly (not from within setWriteMode's
  // updater) since React's StrictMode dev-mode double-invokes updaters to
  // check for side effects -- a non-idempotent call like toggleSidebar()
  // inside one would fire twice and cancel itself out.
  function toggleWriteMode() {
    const next = !writeMode
    setWriteMode(next)
    if (next !== sidebarHidden) toggleSidebar()
    try {
      localStorage.setItem(WRITE_MODE_KEY, String(next))
    } catch {
      // Write Mode can remain session-only if storage is unavailable.
    }
  }

  const { openTab, closeTab, lastAutoClosed } = useTabs()
  const { user } = useAuth()

  const [autoCloseNotice, setAutoCloseNotice] = useState<string | null>(null)
  // Keyed on lastAutoClosed?.key (not the tab name) so a second eviction
  // restarts the 10s timer even if it happens to name the same chapter as
  // the one currently showing.
  useEffect(() => {
    if (!lastAutoClosed) return
    setAutoCloseNotice(`Closed oldest tab: ${lastAutoClosed.name}`)
    const timer = setTimeout(() => setAutoCloseNotice(null), 10000)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastAutoClosed?.key])

  const update = useUpdateChapter(id ?? '', chapter?.folderId ?? undefined)
  const del = useDeleteChapter(chapter?.folderId ?? undefined)
  const leaveShare = useLeaveShare()

  useEffect(() => {
    if (chapter) {
      openTab({
        chapterId: chapter.id,
        name: chapter.name,
        folderId: chapter.folderId,
        folderAccessible: chapter.folderAccessible,
        parentChapterId: chapter.parentChapterId,
        parentChapterAccessible: chapter.parentChapterAccessible,
        bookId: chapter.bookId,
      })
    }
  }, [chapter, openTab])

  useEffect(() => {
    pendingContentRef.current = chapter?.contentHtml ?? ''
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter?.id, editorResetKey])

  const saveContent = useDebouncedCallback((html: string) => {
    update.mutate(
      { contentHtml: html, expectedUpdatedAt: chapter?.updatedAt },
      {
        onSuccess: () => setSaveStatus('saved'),
        onError: (err) => (isConflict(err) ? setHasConflict(true) : setSaveStatus('error')),
      },
    )
  }, 1000)

  const saveNotes = useDebouncedCallback((text: string) => {
    update.mutate(
      { notesText: text, expectedUpdatedAt: chapter?.updatedAt },
      {
        onSuccess: () => setSaveStatus('saved'),
        onError: (err) => (isConflict(err) ? setHasConflict(true) : setSaveStatus('error')),
      },
    )
  }, 500)

  if (isLoading) return <p>Loading...</p>
  if (error || !chapter) return <p>Not found, or you don't have access to it.</p>

  async function handleReloadLatest() {
    setHasConflict(false)
    await qc.invalidateQueries({ queryKey: ['chapter', id] })
    setEditorResetKey((k) => k + 1)
    setSaveStatus('saved')
  }

  function handleForceOverwrite() {
    setHasConflict(false)
    setSaveStatus('saving')
    update.mutate(
      { contentHtml: pendingContentRef.current },
      {
        onSuccess: () => setSaveStatus('saved'),
        onError: () => setSaveStatus('error'),
      },
    )
  }

  function handleToggleComplete(completed: boolean) {
    update.mutate({ completed })
  }

  function handleSaveSettings(data: { name: string; description: string; showBookColor: boolean }) {
    setSaveStatus('saving')
    update.mutate(
      { ...data, expectedUpdatedAt: chapter!.updatedAt },
      {
        onSuccess: () => {
          setSaveStatus('saved')
          setShowSettings(false)
        },
        onError: (err) => {
          if (isConflict(err)) {
            setShowSettings(false)
            setHasConflict(true)
          } else {
            setSaveStatus('error')
          }
        },
      },
    )
  }

  function confirmDelete() {
    del.mutate(chapter!.id, {
      onSuccess: () => {
        closeTab(chapter!.id)
        navigate(tabBackTarget(chapter!))
      },
    })
  }

  function confirmLeave() {
    if (!user) return
    leaveShare.mutate(
      { resourceType: 'chapter', resourceId: chapter!.id, userId: user.id },
      {
        onSuccess: () => {
          closeTab(chapter!.id)
          navigate('/')
        },
      },
    )
  }

  return (
    <div id="chapter_page">
      <div id="chapter_area">
        {!writeMode && <ChapterTabs />}
        {!writeMode && (
          <header className="chapter-header">
            <div className="chapter-title-group">
              {(chapter.parentChapterId !== null ? chapter.parentChapterAccessible : chapter.folderAccessible) && (
                <Link className="chapter-back" to={tabBackTarget(chapter)} aria-label="Back" title="Back">
                  <span aria-hidden="true">&#8592;</span>
                </Link>
              )}
              <h1>{chapter.name}</h1>
              {autoCloseNotice && (
                <span className="chapter-title-notice" role="status">
                  {autoCloseNotice}
                </span>
              )}
            </div>
            <div className="chapter-actions" aria-label="Chapter actions">
              {presentUsers && presentUsers.length > 0 && (
                <span className="chapter-presence" title={presentUsers.map((u) => u.username).join(', ')}>
                  Also here: {presentUsers.map((u) => u.username).join(', ')}
                </span>
              )}
              <button className="chapter-action" type="button" onClick={() => setShowHistory(true)}>
                History
              </button>
              <Link className="chapter-action" to={`/chapters/${chapter.id}/stats`}>
                Stats
              </Link>
              <button className="chapter-action" type="button" onClick={() => setShowSettings(true)}>
                Settings
              </button>
            </div>
          </header>
        )}
        {hasConflict && (
          <div className="chapter-conflict-banner" role="alert">
            <span>This chapter was changed elsewhere since you started editing.</span>
            <div className="chapter-conflict-actions">
              <button type="button" className="chapter-action primary" onClick={handleReloadLatest}>
                Reload latest
              </button>
              <button type="button" className="chapter-action" onClick={handleForceOverwrite}>
                Keep my version
              </button>
            </div>
          </div>
        )}
        {showSettings && (
          <ChapterSettingsModal
            chapter={chapter}
            saving={update.isPending}
            onClose={() => setShowSettings(false)}
            onSave={handleSaveSettings}
            onDelete={() => setConfirmAction('delete')}
            onLeave={chapter.directShare ? () => setConfirmAction('leave') : undefined}
            onToggleComplete={handleToggleComplete}
            canEdit={chapter.role !== 'viewer'}
          />
        )}
        {confirmAction === 'delete' && (
          <ConfirmModal
            title="Delete chapter"
            message={`Delete chapter "${chapter.name}"? This cannot be undone.`}
            confirmLabel="Delete"
            pending={del.isPending}
            onConfirm={confirmDelete}
            onCancel={() => setConfirmAction(null)}
          />
        )}
        {confirmAction === 'leave' && (
          <ConfirmModal
            title="Leave chapter"
            message={`Leave chapter "${chapter.name}"? You'll lose access unless re-shared.`}
            confirmLabel="Leave"
            pending={leaveShare.isPending}
            onConfirm={confirmLeave}
            onCancel={() => setConfirmAction(null)}
          />
        )}
        {showHistory && (
          <ChapterHistoryModal
            chapterId={chapter.id}
            currentContentHtml={pendingContentRef.current}
            currentWordCount={wordCount}
            onClose={() => setShowHistory(false)}
            onRestored={() => {
              setSaveStatus('saved')
              setEditorResetKey((k) => k + 1)
            }}
          />
        )}
        <ChapterEditor
          key={`${chapter.id}-${editorResetKey}`}
          chapterId={chapter.id}
          initialHtml={chapter.contentHtml}
          onChange={(html) => {
            pendingContentRef.current = html
            setSaveStatus('saving')
            saveContent(html)
          }}
          onWordCountChange={(count) => {
            wordCountRef.current = count
            setWordCount(count)
          }}
          onActivity={({ typedWords, pastedWords, deletedWords }) => {
            typedWordsTotalRef.current += typedWords
            pastedWordsTotalRef.current += pastedWords
            deletedWordsTotalRef.current += deletedWords
          }}
          onTypingInput={() => {
            hadTypingSinceHeartbeatRef.current = true
          }}
          bookColor={chapter.bookColor}
          writeMode={writeMode}
          onToggleWriteMode={toggleWriteMode}
          completed={chapter.completedAt !== null}
          onToggleComplete={chapter.role !== 'viewer' ? () => handleToggleComplete(chapter.completedAt === null) : undefined}
          onNavigateInternalReference={(route) => navigate(route)}
          findRequest={findRequest}
          onFindHandled={handleContentFindHandled}
          journalEntryRequest={journalEntryRequest}
          onJournalEntryHandled={handleJournalEntryHandled}
        />
        {staleSearchMatch && (
          <div className="search-stale-notice" role="status">
            {STALE_SEARCH_MATCH_MESSAGE}
          </div>
        )}
        <footer className="chapter-statusbar" aria-live="polite">
          {settings?.showWordCount && (
            <span className="chapter-writing-stats">
              <span>Words: {wordCount.toLocaleString()}</span>
              {/* No WPM sample yet (< MIN_WPM_TYPED_WORDS typed or <
                  MIN_WPM_ACTIVE_SECONDS active, see services.calculate_wpm)
                  means averageWpm is null -- the label and separator are
                  omitted entirely rather than showing a premature "Avg WPM:
                  —", and simply appear once enough data exists. */}
              {settings.showAverageWpm && averageWpm !== null && (
                <>
                  <span aria-hidden="true">·</span>
                  <span>Avg WPM: {averageWpm.toFixed(1)}</span>
                </>
              )}
            </span>
          )}
          <span className={`save-status ${saveStatus}`}>
            <span className="save-status-dot" aria-hidden="true" />
            {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'error' ? 'Could not save' : 'Saved'}
          </span>
        </footer>
      </div>
      {blocker.state === 'blocked' && (
        <div className="settings-leave-overlay" role="presentation">
          <div className="settings-leave-dialog" role="dialog" aria-modal="true" aria-labelledby="chapter-leave-title">
            <h2 id="chapter-leave-title">Leave without saving?</h2>
            <p>This chapter hasn't finished saving yet. Copy its text now if you want a safety copy before you go.</p>
            <div className="settings-leave-actions">
              <button type="button" className="settings-secondary-action" onClick={copyChapterText}>
                {copyStatus === 'copied' ? 'Copied!' : copyStatus === 'error' ? 'Copy failed' : 'Copy chapter text'}
              </button>
              <button type="button" className="settings-primary-action" onClick={() => blocker.proceed()} autoFocus>
                Leave without saving
              </button>
              <button type="button" className="settings-dialog-cancel" onClick={() => blocker.reset()}>
                Stay on this page
              </button>
            </div>
          </div>
        </div>
      )}
      <div id="notes_sidebar" className={notesCollapsed ? 'collapsed' : undefined}>
        {notesCollapsed ? (
          <button
            type="button"
            className="sidebar-reveal"
            onClick={toggleNotesCollapsed}
            aria-label="Show notes"
            title="Show notes"
          >
            ◀
          </button>
        ) : (
          <div className="notes-header">
            <div className="notes-header-left">
              <button
                type="button"
                className="notes-toggle"
                onClick={toggleNotesCollapsed}
                aria-label="Hide notes"
                title="Hide notes"
              >
                <span aria-hidden="true">→</span>
              </button>
              <div>
                <h2>Notes</h2>
                <p>Ideas for this chapter</p>
              </div>
            </div>
            <div className="notes-header-actions">
              <button type="button" className="notes-copy" onClick={copyNotesText} title="Copy all notes">
                {notesCopyStatus === 'copied' ? 'Copied!' : notesCopyStatus === 'error' ? 'Copy failed' : 'Copy all'}
              </button>
            </div>
          </div>
        )}
        <div className="notes-split" ref={notesSplitRef}>
          <textarea
            id="notes_editor"
            ref={notesRef}
            aria-label="Chapter notes"
            placeholder="Ideas, reminders, research…"
            defaultValue={chapter.notesText}
            onChange={(e) => {
              setSaveStatus('saving')
              saveNotes(e.target.value)
            }}
          />
          {subChapters && subChapters.chapters.length > 0 && (
            <>
              <div
                className="notes-vertical-resizer"
                role="separator"
                aria-orientation="horizontal"
                aria-label="Resize sub-chapters panel"
                onPointerDown={handleResizerPointerDown}
                onPointerMove={handleResizerPointerMove}
                onPointerUp={handleResizerPointerUp}
              />
              <div
                className="sub-chapters-panel"
                style={subChaptersPanelHeight !== null ? { flex: `0 1 ${subChaptersPanelHeight}px`, maxHeight: 'none' } : undefined}
              >
                <div className="sub-chapters-panel-header">Sub-chapters</div>
                <ul className="sub-chapters-list">
                  {subChapters.chapters.map((c) => (
                    <li key={c.id}>
                      <Link to={`/chapters/${c.id}`}>{c.name}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
