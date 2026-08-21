import { useCallback, useEffect, useRef } from 'react'

export function useDebouncedCallback<Args extends unknown[]>(fn: (...args: Args) => void, delayMs: number) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return useCallback(
    (...args: Args) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => fnRef.current(...args), delayMs)
    },
    [delayMs],
  )
}
