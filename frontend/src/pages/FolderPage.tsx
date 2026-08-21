import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  useFolder,
  useBook,
  useUpdateFolder,
  useDeleteFolder,
  useCreateFolder,
  useCreateChapter,
  useReorderFolderChildren,
  useSettings,
  useUpdateSettings,
} from '../api/hooks'
import { useDragReorder } from '../hooks/useDragReorder'
import { EMPTY_ARRAY } from '../api/constants'
import { ApiError } from '../api/client'
import CollaboratorsPanel from '../components/CollaboratorsPanel'
import FolderSettingsModal from '../components/FolderSettingsModal'

export default function FolderPage() {
  const { folderId } = useParams()
  const id = folderId ? Number(folderId) : undefined
  const { data: folder, isLoading, error } = useFolder(id)
  const { data: settings } = useSettings()
  const isBook = folder?.parentId === null
  const { data: book } = useBook(isBook ? id : undefined)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [newSubfolderName, setNewSubfolderName] = useState('')
  const [newChapterName, setNewChapterName] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (searchParams.get('settings') !== '1') return
    setShowSettings(true)
    const next = new URLSearchParams(searchParams)
    next.delete('settings')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const update = useUpdateFolder(id ?? 0, folder?.parentId ?? null)
  const del = useDeleteFolder(folder?.parentId ?? null)
  const createFolder = useCreateFolder(id ?? 0)
  const createChapter = useCreateChapter(id ?? 0)
  const reorder = useReorderFolderChildren(id ?? 0)
  const updateSettings = useUpdateSettings()

  const subfolderDrag = useDragReorder(folder?.folders ?? EMPTY_ARRAY, (order) => reorder.mutate({ type: 'folder', order }))
  const chapterDrag = useDragReorder(folder?.chapters ?? EMPTY_ARRAY, (order) => reorder.mutate({ type: 'chapter', order }))
  const closedFolderIds = new Set(settings?.closedFolderIds ?? [])
  const closedChapterIds = new Set(settings?.closedChapterIds ?? [])

  if (isLoading) return <p>Loading...</p>
  if (error || !folder) return <p>Not found, or you don't have access to it.</p>

  async function handleCreateSubfolder(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await createFolder.mutateAsync({ name: newSubfolderName })
      setNewSubfolderName('')
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to create folder')
    }
  }

  async function handleCreateChapter(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      const chapter = await createChapter.mutateAsync({ name: newChapterName })
      setNewChapterName('')
      navigate(`/chapters/${chapter.id}`)
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to create chapter')
    }
  }

  function handleSaveSettings(data: { name: string; description: string }) {
    update.mutate(data, { onSuccess: () => setShowSettings(false) })
  }

  function handleDelete() {
    const label = isBook ? 'book' : 'sub-folder'
    if (window.confirm(`Delete this ${label} "${folder!.name}"? This cannot be undone.`)) {
      const parentId = folder!.parentId
      del.mutate(folder!.id, {
        onSuccess: () => navigate(parentId ? `/folders/${parentId}` : '/'),
      })
    }
  }

  function toggleSubfolderOpen(folderId: number, isOpen: boolean) {
    const current = settings?.closedFolderIds ?? []
    updateSettings.mutate({
      closedFolderIds: isOpen ? [...current, folderId] : current.filter((id) => id !== folderId),
    })
  }

  function toggleChapterOpen(chapterId: number, isOpen: boolean) {
    const current = settings?.closedChapterIds ?? []
    updateSettings.mutate({
      closedChapterIds: isOpen ? [...current, chapterId] : current.filter((id) => id !== chapterId),
    })
  }

  return (
    <div className="folder-page">
      <header className="folder-page-header">
        <div className="folder-page-heading">
          <div className="folder-eyebrow">
            {!isBook && folder.parentId ? <Link to={`/folders/${folder.parentId}`}>&larr; Parent folder</Link> : 'Book'}
          </div>
          <h1>{folder.name}</h1>
          {folder.author && <p className="folder-author">by {folder.author}</p>}
          {folder.description && <p className="folder-description">{folder.description}</p>}
        </div>
        <div className="folder-page-actions" aria-label={`${isBook ? 'Book' : 'Sub-folder'} actions`}>
          {isBook ? (
            book?.role !== 'viewer' && (
              <Link className="folder-action" to={`/folders/${folder.id}/settings`}>Settings</Link>
            )
          ) : (
            <button type="button" className="folder-action" onClick={() => setShowSettings(true)}>Settings</button>
          )}
          {isBook && <Link className="folder-action" to={`/folders/${folder.id}/stats`}>Stats</Link>}
          {isBook && <a className="folder-action" href={`/api/books/${folder.bookId}/export.docx`}>Export .docx</a>}
          {(!isBook || book?.role === 'owner') && (
            <button type="button" className="folder-action danger" onClick={handleDelete}>
              Delete
            </button>
          )}
        </div>
      </header>

      {showSettings && (
        <FolderSettingsModal
          folder={folder}
          saving={update.isPending}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
        />
      )}

      {formError && (
        <ul className="flashes">
          <li>{formError}</li>
        </ul>
      )}

      <section className="folder-section">
        <div className="folder-section-header">
          <div>
            <h2>Sub-folders</h2>
            <p>Keep related chapters together.</p>
          </div>
          <span className="folder-count">{folder.folders.length}</span>
        </div>
        {folder.folders.length > 0 ? (
          <ul className="folder-item-list sortable">
            {subfolderDrag.order.map((f, idx) => {
              const isOpen = !closedFolderIds.has(f.id)
              return (
                <li
                  key={f.id}
                  draggable
                  onDragStart={() => subfolderDrag.onDragStart(idx)}
                  onDragOver={(e) => subfolderDrag.onDragOver(idx, e)}
                  onDrop={subfolderDrag.onDrop}
                >
                  <span className="drag-handle" aria-hidden="true">⋮⋮</span>
                  <div className="folder-item-name">
                    {isOpen ? <Link to={`/folders/${f.id}`}>{f.name}</Link> : <span>{f.name}</span>}
                    {f.description && <p className="folder-item-description">{f.description}</p>}
                    {!isOpen && <small>Hidden from sidebar</small>}
                  </div>
                  <button type="button" className="item-visibility-button" onClick={() => toggleSubfolderOpen(f.id, isOpen)}>
                    {isOpen ? 'Close' : 'Open'}
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="folder-empty-state">No sub-folders yet.</p>
        )}
        <form onSubmit={handleCreateSubfolder} className="folder-create-form">
          <input
            type="text"
            placeholder="New sub-folder name"
            aria-label="New sub-folder name"
            value={newSubfolderName}
            onChange={(e) => setNewSubfolderName(e.target.value)}
            required
          />
          <button type="submit" disabled={createFolder.isPending}>Add sub-folder</button>
        </form>
      </section>

      <section className="folder-section">
        <div className="folder-section-header">
          <div>
            <h2>Chapters</h2>
            <p>Drag chapters to change their order.</p>
          </div>
          <span className="folder-count">{folder.chapters.length}</span>
        </div>
        {folder.chapters.length > 0 ? (
          <ul className="folder-item-list sortable">
            {chapterDrag.order.map((c, idx) => {
              const isOpen = !closedChapterIds.has(c.id)
              return (
                <li
                  key={c.id}
                  draggable
                  onDragStart={() => chapterDrag.onDragStart(idx)}
                  onDragOver={(e) => chapterDrag.onDragOver(idx, e)}
                  onDrop={chapterDrag.onDrop}
                >
                  <span className="drag-handle" aria-hidden="true">⋮⋮</span>
                  <div className="folder-item-name">
                    {isOpen ? <Link to={`/chapters/${c.id}`}>{c.name}</Link> : <span>{c.name}</span>}
                    {c.description && <p className="folder-item-description">{c.description}</p>}
                    {!isOpen && <small>Hidden from sidebar</small>}
                  </div>
                  <button type="button" className="item-visibility-button" onClick={() => toggleChapterOpen(c.id, isOpen)}>
                    {isOpen ? 'Close' : 'Open'}
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="folder-empty-state">No chapters yet.</p>
        )}
        <form onSubmit={handleCreateChapter} className="folder-create-form">
          <input
            type="text"
            placeholder="New chapter name"
            aria-label="New chapter name"
            value={newChapterName}
            onChange={(e) => setNewChapterName(e.target.value)}
            required
          />
          <button type="submit" disabled={createChapter.isPending}>Add chapter</button>
        </form>
      </section>

      {isBook && book?.role === 'owner' && <CollaboratorsPanel bookId={folder.id} />}
    </div>
  )
}
