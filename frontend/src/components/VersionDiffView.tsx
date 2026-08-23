import { useMemo } from 'react'
import { diffVersionsHtml, type DiffPart } from '../utils/versionDiff'

/** Side-by-side word-level diff between two chapter versions' rendered
 * content -- shared between ChapterHistoryModal (compact) and ChapterDiffPage
 * (full page) so the actual diff rendering only exists in one place. */
export default function VersionDiffView({
  fromLabel,
  toLabel,
  fromHtml,
  toHtml,
}: {
  fromLabel: string
  toLabel: string
  fromHtml: string
  toHtml: string
}) {
  const diffParts = useMemo<DiffPart[]>(() => diffVersionsHtml(fromHtml, toHtml), [fromHtml, toHtml])

  return (
    <div className="history-diff">
      <div className="history-diff-side">
        <div className="history-diff-side-label">{fromLabel}</div>
        <div className="history-diff-pane">
          {diffParts.map((part, i) =>
            part.added ? null : (
              <span key={i} className={part.removed ? 'history-diff-removed' : undefined}>
                {part.value}
              </span>
            ),
          )}
        </div>
      </div>
      <div className="history-diff-side">
        <div className="history-diff-side-label">{toLabel}</div>
        <div className="history-diff-pane">
          {diffParts.map((part, i) =>
            part.removed ? null : (
              <span key={i} className={part.added ? 'history-diff-added' : undefined}>
                {part.value}
              </span>
            ),
          )}
        </div>
      </div>
    </div>
  )
}
