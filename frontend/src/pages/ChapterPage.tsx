import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useChapter,
  useUpdateChapter,
  useDeleteChapter,
  useChapterPresence,
  useChapterPresenceHeartbeat,
} from '../api/hooks'
import { ApiError } from '../api/client'
import { useDebouncedCallback } from '../hooks/useDebouncedCallback'
import { useBodyClass } from '../hooks/useBodyClass'
import { useTabs } from '../context/TabsContext'
import ChapterEditor from '../components/ChapterEditor'
import ChapterTabs from '../components/ChapterTabs'
import ChapterSettingsModal from '../components/ChapterSettingsModal'
import ChapterHistoryModal from '../components/ChapterHistoryModal'

const NOTES_COLLAPSED_KEY = 'calwriter:notesCollapsed'
const PRESENCE_HEARTBEAT_MS = 20000

function isConflict(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409
}

export default function ChapterPage() {
  const { chapterId } = useParams()
  const id = chapterId ? Number(chapterId) : undefined
  const { data: chapter, isLoading, error } = useChapter(id)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const qc = useQueryClient()
  useBodyClass('chapter-view')
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

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
  const pendingContentRef = useRef('')

  const heartbeat = useChapterPresenceHeartbeat(id)
  const { data: presentUsers } = useChapterPresence(id)

  useEffect(() => {
    if (!id) return
    heartbeat.mutate()
    const interval = setInterval(() => heartbeat.mutate(), PRESENCE_HEARTBEAT_MS)
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

  const { openTab, closeTab } = useTabs()

  const update = useUpdateChapter(id ?? 0, chapter?.folderId ?? 0)
  const del = useDeleteChapter(chapter?.folderId ?? 0)

  useEffect(() => {
    if (chapter) {
      openTab({ chapterId: chapter.id, name: chapter.name, folderId: chapter.folderId, bookId: chapter.bookId })
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

  function handleSaveSettings(data: { name: string; description: string }) {
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

  function handleDelete() {
    if (window.confirm(`Delete chapter "${chapter!.name}"? This cannot be undone.`)) {
      del.mutate(chapter!.id, {
        onSuccess: () => {
          closeTab(chapter!.id)
          navigate(`/folders/${chapter!.folderId}`)
        },
      })
    }
  }

  return (
    <div id="chapter_page">
      <div id="chapter_area">
        <ChapterTabs />
        <header className="chapter-header">
          <div className="chapter-title-group">
            <Link className="chapter-back" to={`/folders/${chapter.folderId}`} aria-label="Back to folder" title="Back to folder">
              <span aria-hidden="true">&#8592;</span>
            </Link>
            <h1>{chapter.name}</h1>
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
            <button className="chapter-action" type="button" onClick={() => setShowSettings(true)}>
              Settings
            </button>
          </div>
        </header>
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
            onDelete={handleDelete}
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
          onWordCountChange={setWordCount}
        />
        <footer className="chapter-statusbar" aria-live="polite">
          <span>{wordCount.toLocaleString()} {wordCount === 1 ? 'word' : 'words'}</span>
          <span className={`save-status ${saveStatus}`}>
            <span className="save-status-dot" aria-hidden="true" />
            {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'error' ? 'Could not save' : 'Saved'}
          </span>
        </footer>
      </div>
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
            <div>
              <h2>Notes</h2>
              <p>Ideas for this chapter</p>
            </div>
            <button
              type="button"
              className="notes-toggle"
              onClick={toggleNotesCollapsed}
              aria-label="Hide notes"
              title="Hide notes"
            >
              <span aria-hidden="true">→</span>
            </button>
          </div>
        )}
        <textarea
          id="notes_editor"
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
