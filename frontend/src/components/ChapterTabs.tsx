import { useNavigate, useParams } from 'react-router-dom'
import { useTabs, type OpenTab } from '../context/TabsContext'
import { useBooks } from '../api/hooks'

export default function ChapterTabs() {
  const { tabs, closeTab } = useTabs()
  const { data: books } = useBooks()
  const { chapterId } = useParams()
  const activeId = chapterId
  const navigate = useNavigate()

  if (tabs.length === 0) return null

  const colorByBookId = new Map(books?.map((book) => [book.id, book.color || '#999999']))

  function handleClose(e: React.MouseEvent, tab: OpenTab, index: number) {
    e.stopPropagation()
    closeTab(tab.chapterId)
    if (tab.chapterId !== activeId) return
    const remaining = tabs.filter((t) => t.chapterId !== tab.chapterId)
    const next = remaining[index] ?? remaining[index - 1]
    if (next) {
      navigate(`/chapters/${next.chapterId}`)
    } else {
      navigate(tab.folderAccessible ? `/folders/${tab.folderId}` : '/')
    }
  }

  return (
    <div className="chapter-tabs" role="tablist" aria-label="Open chapters">
      {tabs.map((tab, index) => (
        <div
          key={tab.chapterId}
          className={`chapter-tab${tab.chapterId === activeId ? ' active' : ''}`}
          role="tab"
          tabIndex={0}
          aria-selected={tab.chapterId === activeId}
          onClick={() => navigate(`/chapters/${tab.chapterId}`)}
        >
          <span
            className="book-color-dot"
            style={{ backgroundColor: colorByBookId.get(tab.bookId) ?? '#999999' }}
            aria-hidden="true"
          />
          <span className="chapter-tab-name">{tab.name}</span>
          <button
            type="button"
            className="chapter-tab-close"
            onClick={(e) => handleClose(e, tab, index)}
            aria-label={`Close ${tab.name}`}
            title={`Close ${tab.name}`}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
