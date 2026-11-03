export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let csrfToken: string | null = null
let refreshCsrfPromise: Promise<string | null> | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

async function refreshCsrfToken(): Promise<string | null> {
  if (refreshCsrfPromise) {
    return refreshCsrfPromise
  }
  refreshCsrfPromise = (async () => {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' })
      if (!res.ok) return null
      const data = await res.json()
      if (data && typeof data === 'object' && typeof data.csrfToken === 'string') {
        csrfToken = data.csrfToken
        return data.csrfToken
      }
      return null
    } catch {
      return null
    } finally {
      refreshCsrfPromise = null
    }
  })()
  return refreshCsrfPromise
}

interface RequestOptions {
  method?: string
  body?: unknown
  isForm?: boolean
  _isRetry?: boolean
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, isForm = false } = options
  const headers: Record<string, string> = {}
  const mutating = method !== 'GET'
  if (mutating && csrfToken) {
    headers['X-CSRFToken'] = csrfToken
  }
  let payload: BodyInit | undefined
  if (body !== undefined && isForm) {
    payload = body as FormData
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: payload,
    credentials: 'include',
  })

  if (res.status === 204) {
    return undefined as T
  }

  const contentType = res.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await res.json() : await res.text()

  if (!res.ok) {
    const isCsrfError =
      res.status === 400 &&
      mutating &&
      !options._isRetry &&
      ((typeof data === 'object' &&
        data !== null &&
        (('code' in data && (data as { code?: unknown }).code === 'csrf_error') ||
          ('error' in data && String((data as { error?: unknown }).error).toLowerCase().includes('csrf')))) ||
        (typeof data === 'string' && data.toLowerCase().includes('csrf')))

    if (isCsrfError) {
      const freshToken = await refreshCsrfToken()
      if (freshToken) {
        return request<T>(path, { ...options, _isRetry: true })
      }
    }

    const message = typeof data === 'object' && data && 'error' in data ? String(data.error) : `Request failed (${res.status})`
    throw new ApiError(res.status, message)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form, isForm: true }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

// A same-origin GET that responds with Content-Disposition: attachment (any
// of the /api/*/export.* routes) downloads cleanly via a synthetic <a> click.
// Assigning window.location.href directly also works in most browsers, but
// it's a real navigation attempt underneath and can flash/log as a failed
// load once the browser aborts it in favor of the download -- an <a> click
// never starts that navigation in the first place.
export function triggerDownload(path: string) {
  const a = document.createElement('a')
  a.href = `/api${path}`
  document.body.appendChild(a)
  a.click()
  a.remove()
}
