import { useEffect } from 'react'

// Mirrors the old Jinja layout's {% block body_class %} -- some pages' CSS
// (see body.chapter-view rules in index.css) depends on a class on <body>
// itself, which lives outside React's render tree.
export function useBodyClass(className: string) {
  useEffect(() => {
    document.body.classList.add(className)
    return () => document.body.classList.remove(className)
  }, [className])
}
