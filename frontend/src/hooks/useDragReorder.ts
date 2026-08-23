import { useEffect, useRef, useState, type DragEvent } from 'react'

export function useDragReorder<T extends { id: string }>(items: readonly T[], onReorder: (orderedIds: string[]) => void) {
  const [order, setOrder] = useState<readonly T[]>(items)
  const dragIndex = useRef<number | null>(null)

  // Callers often pass an inline fallback (e.g. `data?.items ?? []`), which is
  // a new array reference every render even when the actual ids are unchanged.
  // Bail out on matching content (not just matching reference) so this doesn't
  // set state -- and therefore doesn't re-render -- when nothing really changed.
  // Otherwise: new []  -> setOrder -> re-render -> new [] -> ... infinite loop.
  useEffect(() => {
    setOrder((prev) => {
      const sameIds = prev.length === items.length && prev.every((p, i) => p.id === items[i]?.id)
      if (!sameIds) return items
      // Same ids in the same positions -- keep this hook's own order (so an
      // in-progress drag or a reorder that just landed isn't clobbered by a
      // refetch), but still pick up each item's latest field values (e.g. a
      // "Complete" toggle) from the fresh data rather than displaying
      // whatever was true when this order was last set.
      const byId = new Map(items.map((item) => [item.id, item]))
      const refreshed = prev.map((p) => byId.get(p.id) ?? p)
      const changed = refreshed.some((r, i) => r !== prev[i])
      return changed ? refreshed : prev
    })
  }, [items])

  function onDragStart(index: number) {
    dragIndex.current = index
  }

  function onDragOver(index: number, e: DragEvent) {
    e.preventDefault()
    if (dragIndex.current === null || dragIndex.current === index) return
    const from = dragIndex.current
    setOrder((prev) => {
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(index, 0, moved)
      return next
    })
    dragIndex.current = index
  }

  function onDrop() {
    dragIndex.current = null
    onReorder(order.map((item) => item.id))
  }

  return { order, onDragStart, onDragOver, onDrop }
}
