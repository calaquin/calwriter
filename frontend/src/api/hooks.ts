import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  Book,
  FolderSummary,
  FolderDetail,
  ChapterSummary,
  ChapterDetail,
  ChapterVersionSummary,
  ChapterVersionDetail,
  PresenceUser,
  UserSettings,
  Collaborator,
  SearchResult,
  BookStats,
  Invite,
} from './types'

export function useBooks() {
  return useQuery({ queryKey: ['books'], queryFn: () => api.get<Book[]>('/books') })
}

export function useBook(bookId: number | undefined) {
  return useQuery({
    queryKey: ['book', bookId],
    queryFn: () => api.get<Book>(`/books/${bookId}`),
    enabled: bookId !== undefined,
  })
}

export function useFolder(folderId: number | undefined) {
  return useQuery({
    queryKey: ['folder', folderId],
    queryFn: () => api.get<FolderDetail>(`/folders/${folderId}`),
    enabled: folderId !== undefined,
  })
}

export function useChapter(chapterId: number | undefined) {
  return useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
    enabled: chapterId !== undefined,
  })
}

export function useSettings() {
  return useQuery({ queryKey: ['settings'], queryFn: () => api.get<UserSettings>('/me/settings') })
}

export function useCollaborators(bookId: number | undefined) {
  return useQuery({
    queryKey: ['collaborators', bookId],
    queryFn: () => api.get<Collaborator[]>(`/books/${bookId}/collaborators`),
    enabled: bookId !== undefined,
  })
}

export function useChangelog() {
  return useQuery({ queryKey: ['changelog'], queryFn: () => api.get<{ content: string }>('/changelog') })
}

export function useSearch(query: string) {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => api.get<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 0,
  })
}

export function useBookStats(bookId: number | undefined, days: number) {
  return useQuery({
    queryKey: ['stats', bookId, days],
    queryFn: () => api.get<BookStats>(`/books/${bookId}/stats?days=${days}`),
    enabled: bookId !== undefined,
  })
}

// -------------------------------------------------------------- mutations --

export function useCreateBook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string }) => api.post<Book>('/books', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['books'] }),
  })
}

export function useCreateBookWizard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { title: string; chapters: string; author: string; color: string; extras: string[] }) =>
      api.post<Book>('/books/wizard', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['books'] }),
  })
}

export function useExportDatabase() {
  return useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/export', { credentials: 'include' })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const disposition = res.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : 'calwriter-export.calwdb'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    },
  })
}

export function useImportDatabase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.postForm<{ imported: number }>('/import', form)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['books'] }),
  })
}

export function useUpdateBook(bookId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<{ name: string; description: string; author: string; color: string }>) =>
      api.patch<Book>(`/books/${bookId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['books'] })
      qc.invalidateQueries({ queryKey: ['book', bookId] })
      qc.invalidateQueries({ queryKey: ['folder', bookId] })
    },
  })
}

export function useDeleteBook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (bookId: number) => api.del<void>(`/books/${bookId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['books'] }),
  })
}

export function useCreateFolder(parentId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string }) => api.post<FolderSummary>('/folders', { ...data, parentId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', parentId] }),
  })
}

export function useUpdateFolder(folderId: number, parentId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<{ name: string; description: string; author: string }>) =>
      api.patch<FolderSummary>(`/folders/${folderId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
      if (parentId !== null) qc.invalidateQueries({ queryKey: ['folder', parentId] })
    },
  })
}

export function useDeleteFolder(parentId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (folderId: number) => api.del<void>(`/folders/${folderId}`),
    onSuccess: () => {
      if (parentId !== null) qc.invalidateQueries({ queryKey: ['folder', parentId] })
      qc.invalidateQueries({ queryKey: ['books'] })
    },
  })
}

export function useCreateChapter(folderId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string }) => api.post<ChapterSummary>('/chapters', { ...data, folderId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', folderId] }),
  })
}

export function useUpdateChapter(chapterId: number, folderId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (
      data: Partial<{
        name: string
        description: string
        contentHtml: string
        notesText: string
        expectedUpdatedAt: string
      }>,
    ) => api.patch<ChapterDetail>(`/chapters/${chapterId}`, data),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', chapterId], updated)
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
    },
  })
}

export function useMoveChapter() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { chapterId: number; sourceFolderId: number; folderId: number }) =>
      api.patch<ChapterDetail>(`/chapters/${vars.chapterId}`, { folderId: vars.folderId }),
    onSuccess: (updated, vars) => {
      qc.setQueryData(['chapter', updated.id], updated)
      qc.invalidateQueries({ queryKey: ['folder', vars.sourceFolderId] })
      qc.invalidateQueries({ queryKey: ['folder', updated.folderId] })
    },
  })
}

export function useRenameChapter(folderId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { chapterId: number; name: string }) =>
      api.patch<ChapterDetail>(`/chapters/${vars.chapterId}`, { name: vars.name }),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', updated.id], updated)
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
    },
  })
}

export function useDeleteChapter(folderId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (chapterId: number) => api.del<void>(`/chapters/${chapterId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', folderId] }),
  })
}

export function useChapterVersions(chapterId: number | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['chapterVersions', chapterId],
    queryFn: () => api.get<ChapterVersionSummary[]>(`/chapters/${chapterId}/versions`),
    enabled: chapterId !== undefined && enabled,
  })
}

export function useChapterVersion(chapterId: number | undefined, versionId: number | undefined) {
  return useQuery({
    queryKey: ['chapterVersion', chapterId, versionId],
    queryFn: () => api.get<ChapterVersionDetail>(`/chapters/${chapterId}/versions/${versionId}`),
    enabled: chapterId !== undefined && versionId !== undefined,
  })
}

export function useRestoreChapterVersion(chapterId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: number) => api.post<ChapterDetail>(`/chapters/${chapterId}/versions/${versionId}/restore`),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', chapterId], updated)
      qc.invalidateQueries({ queryKey: ['chapterVersions', chapterId] })
    },
  })
}

export function useChapterPresence(chapterId: number | undefined) {
  return useQuery({
    queryKey: ['chapterPresence', chapterId],
    queryFn: () => api.get<PresenceUser[]>(`/chapters/${chapterId}/presence`),
    enabled: chapterId !== undefined,
    refetchInterval: 15000,
  })
}

export function useChapterPresenceHeartbeat(chapterId: number | undefined) {
  return useMutation({
    mutationFn: () => api.post<void>(`/chapters/${chapterId}/presence`),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<UserSettings>) => api.patch<UserSettings>('/me/settings', data),
    onSuccess: (updated) => qc.setQueryData(['settings'], updated),
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { currentPassword: string; newPassword: string }) => api.patch<void>('/me/password', data),
  })
}

export function useCreateInvite() {
  return useMutation({
    mutationFn: () => api.post<Invite>('/invites'),
  })
}

export function useReorderFolderChildren(folderId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { type: 'folder' | 'chapter'; order: number[] }) =>
      api.post<void>(`/folders/${folderId}/reorder`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', folderId] }),
  })
}

export function useReorderBooks() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (order: number[]) => api.patch<UserSettings>('/me/settings', { bookOrder: order }),
    onSuccess: (updated) => {
      qc.setQueryData(['settings'], updated)
      qc.invalidateQueries({ queryKey: ['books'] })
    },
  })
}

export function useAddCollaborator(bookId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { username: string; role: 'editor' | 'viewer' }) =>
      api.post<Collaborator>(`/books/${bookId}/collaborators`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collaborators', bookId] }),
  })
}

export function useRemoveCollaborator(bookId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: number) => api.del<void>(`/books/${bookId}/collaborators/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collaborators', bookId] }),
  })
}
