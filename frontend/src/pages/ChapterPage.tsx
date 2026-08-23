import { useEffect, useRef, useState } from 'react'
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useChapter,
  useUpdateChapter,
  useDeleteChapter,
  useChapterPresence,
  useChapterPresenceHeartbeat,
  useLeaveShare,
} from '../api/hooks'
import { ApiError } from '../api/client'
import { useDebouncedCallback } from '../hooks/useDebouncedCallback'
import { useBodyClass } from '../hooks/useBodyClass'
import { useTabs } from '../context/TabsContext'
import { useAuth } from '../context/AuthContext'
import { useSidebarVisibility } from '../context/SidebarVisibilityContext'
import ChapterEditor from '../components/ChapterEditor'
import ChapterTabs from '../components/ChapterTabs'
import ChapterSettingsModal from '../components/ChapterSettingsModal'
import ChapterHistoryModal from '../components/ChapterHistoryModal'
import ConfirmModal from '../components/ConfirmModal'
import { copyText } from '../utils/clipboard'

const NOTES_COLLAPSED_KEY = 'calwriter:notesCollapsed'
const WRITE_MODE_KEY = 'calwriter:writeMode'
const PRESENCE_HEARTBEAT_MS = 20000

function isConflict(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409
}

export default function ChapterPage() {
  const { chapterId } = useParams()
  const id = chapterId
  const { data: chapter, isLoading, error } = useChapter(id)
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
  const [editorResetKey, setEditorResetKey] = useState(0)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved')
  const [hasConflict, setHasConflict] = useState(false)
  const [wordCount, setWordCount] = useState(0)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const [notesCopyStatus, setNotesCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const pendingContentRef = useRef('')
  const notesRef = useRef<HTMLTextAreaElement>(null)
  // Mirrors of wordCount/"an edit happened" for the heartbeat interval below.
  // That interval is deliberately created once per chapter (deps: [id], see
  // its own comment) so it never sees fresh state through closure -- refs,
  // updated on every word-count/content change, are what let each 20s tick
  // report live values instead of whatever they were when the interval was
  // created.
  const wordCountRef = useRef(0)
  const typedSinceHeartbeatRef = useRef(false)

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

  useEffect(() => {
    if (!id) return
    function fireHeartbeat() {
      heartbeat.mutate({ wordCount: wordCountRef.current, typed: typedSinceHeartbeatRef.current })
      typedSinceHeartbeatRef.current = false
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

  const update = useUpdateChapter(id ?? '', chapter?.folderId ?? '')
  const del = useDeleteChapter(chapter?.folderId ?? '')
  const leaveShare = useLeaveShare()

  useEffect(() => {
    if (chapter) {
      openTab({
        chapterId: chapter.id,
        name: chapter.name,
        folderId: chapter.folderId,
        folderAccessible: chapter.folderAccessible,
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
        navigate(chapter!.folderAccessible ? `/folders/${chapter!.folderId}` : '/')
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
              {chapter.folderAccessible && (
                <Link className="chapter-back" to={`/folders/${chapter.folderId}`} aria-label="Back to folder" title="Back to folder">
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
            typedSinceHeartbeatRef.current = true
            setSaveStatus('saving')
            saveContent(html)
          }}
          onWordCountChange={(count) => {
            wordCountRef.current = count
            setWordCount(count)
          }}
          bookColor={chapter.bookColor}
          writeMode={writeMode}
          onToggleWriteMode={toggleWriteMode}
          completed={chapter.completedAt !== null}
          onToggleComplete={chapter.role !== 'viewer' ? () => handleToggleComplete(chapter.completedAt === null) : undefined}
        />
        <footer className="chapter-statusbar" aria-live="polite">
          <span>{wordCount.toLocaleString()} {wordCount === 1 ? 'word' : 'words'}</span>
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
      </div>
    </div>
  )
}
