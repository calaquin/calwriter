import { useEffect } from 'react'

// `100dvh` (see body/#sidebar in index.css) is the right unit for "the
// browser's actual visible height, chrome excluded" -- but WebKit tablet
// browsers (iPadOS Safari in particular) have shipped it with real bugs:
// the dvh value can go stale after a client-side route change (this is a
// single-page app -- no full navigation/reload re-triggers the browser's
// own recalculation) or after a toolbar show/hide that isn't accompanied by
// a `resize` event WebKit considers "real". A stale-too-tall value means
// the layout is sized for more room than is actually visible, so content
// pinned to the bottom (the chapter status bar, a page's last scrolled-to
// element) ends up rendered under the browser's own chrome -- unreachable,
// not just visually clipped in a screenshot.
//
// `--app-100dvh` (declared in :root, defaulting to the CSS `100dvh` value
// itself) is the workaround: mirror `window.innerHeight` -- the layout
// viewport, which does reliably fire `resize` on orientation change and
// toolbar show/hide, deliberately not `visualViewport.height` (which also
// shrinks for an on-screen keyboard; keyboard-open resizing is a separate,
// unrelated concern this fix isn't targeting) -- into a px custom property
// on first paint and every subsequent resize/orientation change/pageshow
// (the last for bfcache restores, which don't fire `resize`). CSS then
// prefers this JS-computed value over the raw unit once it's available.
export function useViewportHeightFix() {
  useEffect(() => {
    function apply() {
      document.documentElement.style.setProperty('--app-100dvh', `${window.innerHeight}px`)
    }
    apply()
    window.addEventListener('resize', apply)
    window.addEventListener('orientationchange', apply)
    window.addEventListener('pageshow', apply)
    return () => {
      window.removeEventListener('resize', apply)
      window.removeEventListener('orientationchange', apply)
      window.removeEventListener('pageshow', apply)
    }
  }, [])
}
