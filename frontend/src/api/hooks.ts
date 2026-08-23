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
  Share,
  SharedItem,
  SearchResult,
  WorkspaceStats,
  FolderStats,
  ChapterStats,
  Invite,
  Goal,
  GoalType,
  GoalCadence,
  GoalResourceType,
  FolderTreeIds,
  FolderTreeEntry,
  GoalHistory,
} from './types'

type ShareResourceType = 'folder' | 'chapter'

export function useBooks() {
  return useQuery({ queryKey: ['books'], queryFn: () => api.get<Book[]>('/books') })
}

export function useBook(bookId: string | undefined) {
  return useQuery({
    queryKey: ['book', bookId],
    queryFn: () => api.get<Book>(`/books/${bookId}`),
    enabled: bookId !== undefined,
  })
}

export function useFolder(folderId: string | undefined) {
  return useQuery({
    queryKey: ['folder', folderId],
    queryFn: () => api.get<FolderDetail>(`/folders/${folderId}`),
    enabled: folderId !== undefined,
  })
}

/** Every sub-folder and chapter id nested under a folder -- used to decide
 * whether "Open all" has anything to do (see useOpenAll) before the user
 * clicks it, not just to perform the un-hide itself. */
export function useFolderTreeIds(folderId: string | undefined) {
  return useQuery({
    queryKey: ['folder-tree-ids', folderId],
    queryFn: () => api.get<FolderTreeIds>(`/folders/${folderId}/tree-ids`),
    enabled: folderId !== undefined,
  })
}

/** Every sub-folder and chapter in a book, flattened with depth -- for a
 * picker that needs names, not just ids (see CreateGoalModal). */
export function useFolderTree(folderId: string | undefined) {
  return useQuery({
    queryKey: ['folder-tree', folderId],
    queryFn: () => api.get<FolderTreeEntry[]>(`/folders/${folderId}/tree`),
    enabled: folderId !== undefined,
  })
}

export function useChapter(chapterId: string | undefined) {
  return useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
    enabled: chapterId !== undefined,
  })
}

export function useSettings() {
  return useQuery({ queryKey: ['settings'], queryFn: () => api.get<UserSettings>('/me/settings') })
}

export function useShares(resourceType: ShareResourceType, resourceId: string | undefined) {
  return useQuery({
    queryKey: ['shares', resourceType, resourceId],
    queryFn: () => api.get<Share[]>(`/${resourceType}s/${resourceId}/shares`),
    enabled: resourceId !== undefined,
  })
}

export function useSharedWithMe() {
  return useQuery({ queryKey: ['shared-with-me'], queryFn: () => api.get<SharedItem[]>('/shared-with-me') })
}

/** Revoke a share by resource + target user, without being bound to one
 * resourceId up front -- for a list of many shared items (the "Shared with
 * me" sidebar) where each row leaves a different resource. */
export function useLeaveShare() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      resourceType,
      resourceId,
      userId,
    }: {
      resourceType: ShareResourceType
      resourceId: string
      userId: string
    }) => api.del<void>(`/${resourceType}s/${resourceId}/shares/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shared-with-me'] }),
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

export function useFolderStats(folderId: string | undefined, days: number) {
  return useQuery({
    queryKey: ['stats', 'folder', folderId, days],
    queryFn: () => api.get<FolderStats>(`/folders/${folderId}/stats?days=${days}`),
    enabled: folderId !== undefined,
  })
}

export function useChapterStats(chapterId: string | undefined, days: number) {
  return useQuery({
    queryKey: ['stats', 'chapter', chapterId, days],
    queryFn: () => api.get<ChapterStats>(`/chapters/${chapterId}/stats?days=${days}`),
    enabled: chapterId !== undefined,
  })
}

export function useWorkspaceStats(days: number, enabled = true) {
  return useQuery({
    queryKey: ['stats', 'workspace', days],
    queryFn: () => api.get<WorkspaceStats>(`/stats?days=${days}`),
    enabled,
  })
}

export function useGoals() {
  return useQuery({ queryKey: ['goals'], queryFn: () => api.get<Goal[]>('/goals') })
}

export function useGoalHistory(goalId: string | undefined) {
  return useQuery({
    queryKey: ['goal-history', goalId],
    queryFn: () => api.get<GoalHistory>(`/goals/${goalId}/history`),
    enabled: goalId !== undefined,
  })
}

// -------------------------------------------------------------- mutations --

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

export function useUpdateBook(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (
      data: Partial<{ name: string; description: string; author: string; color: string; showBookColor: boolean }>,
    ) => api.patch<Book>(`/books/${bookId}`, data),
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
    mutationFn: (bookId: string) => api.del<void>(`/books/${bookId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['books'] }),
  })
}

export function useCreateFolder(parentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post<FolderSummary>('/folders', { ...data, parentId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', parentId] }),
  })
}

export function useUpdateFolder(folderId: string, parentId: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<{ name: string; description: string; author: string; showBookColor: boolean }>) =>
      api.patch<FolderSummary>(`/folders/${folderId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
      if (parentId !== null) qc.invalidateQueries({ queryKey: ['folder', parentId] })
    },
  })
}

export function useDeleteFolder(parentId: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (folderId: string) => api.del<void>(`/folders/${folderId}`),
    onSuccess: () => {
      if (parentId !== null) qc.invalidateQueries({ queryKey: ['folder', parentId] })
      qc.invalidateQueries({ queryKey: ['books'] })
    },
  })
}

export function useCreateChapter(folderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post<ChapterSummary>('/chapters', { ...data, folderId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', folderId] }),
  })
}

export function useUpdateChapter(chapterId: string, folderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (
      data: Partial<{
        name: string
        description: string
        contentHtml: string
        notesText: string
        expectedUpdatedAt: string
        completed: boolean
        showBookColor: boolean
      }>,
    ) => api.patch<ChapterDetail>(`/chapters/${chapterId}`, data),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', chapterId], updated)
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
      // Word count / completion state may have just changed, which any
      // words-or-chapters goal targeting this chapter (or an ancestor
      // folder) tracks live -- without this, the sidebar's primary-goal
      // progress bar and the Goals page only caught up on a full reload.
      qc.invalidateQueries({ queryKey: ['goals'] })
    },
  })
}

export function useMoveChapter() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { chapterId: string; sourceFolderId: string; folderId: string }) =>
      api.patch<ChapterDetail>(`/chapters/${vars.chapterId}`, { folderId: vars.folderId }),
    onSuccess: (updated, vars) => {
      qc.setQueryData(['chapter', updated.id], updated)
      qc.invalidateQueries({ queryKey: ['folder', vars.sourceFolderId] })
      qc.invalidateQueries({ queryKey: ['folder', updated.folderId] })
    },
  })
}

export function useRenameChapter(folderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { chapterId: string; name: string }) =>
      api.patch<ChapterDetail>(`/chapters/${vars.chapterId}`, { name: vars.name }),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', updated.id], updated)
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
    },
  })
}

export function useDeleteChapter(folderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (chapterId: string) => api.del<void>(`/chapters/${chapterId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folder', folderId] })
      // Removes the chapter's words/completion from any covering folder
      // goal, and cascade-deletes a goal targeting the chapter directly.
      qc.invalidateQueries({ queryKey: ['goals'] })
    },
  })
}

export function useChapterVersions(chapterId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['chapterVersions', chapterId],
    queryFn: () => api.get<ChapterVersionSummary[]>(`/chapters/${chapterId}/versions`),
    enabled: chapterId !== undefined && enabled,
  })
}

export function useChapterVersion(chapterId: string | undefined, versionId: string | undefined) {
  return useQuery({
    queryKey: ['chapterVersion', chapterId, versionId],
    queryFn: () => api.get<ChapterVersionDetail>(`/chapters/${chapterId}/versions/${versionId}`),
    enabled: chapterId !== undefined && versionId !== undefined,
  })
}

export function useRestoreChapterVersion(chapterId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: string) => api.post<ChapterDetail>(`/chapters/${chapterId}/versions/${versionId}/restore`),
    onSuccess: (updated) => {
      qc.setQueryData(['chapter', chapterId], updated)
      qc.invalidateQueries({ queryKey: ['chapterVersions', chapterId] })
      // Restoring can move the word count up or down, same as a normal edit.
      qc.invalidateQueries({ queryKey: ['goals'] })
    },
  })
}

export function useChapterPresence(chapterId: string | undefined) {
  return useQuery({
    queryKey: ['chapterPresence', chapterId],
    queryFn: () => api.get<PresenceUser[]>(`/chapters/${chapterId}/presence`),
    enabled: chapterId !== undefined,
    refetchInterval: 15000,
  })
}

export function useChapterPresenceHeartbeat(chapterId: string | undefined) {
  return useMutation({
    mutationFn: (vars: { wordCount: number; typed: boolean }) =>
      api.post<void>(`/chapters/${chapterId}/presence`, vars),
  })
}

/** Quick "Complete" toggle usable from a chapter-list row (FolderPage,
 * FolderTreeNode, the stale-chapters stats list) without opening Chapter
 * Settings -- same PATCH the settings modal's checkbox already uses. Not
 * bound to one folderId up front (unlike useUpdateChapter) since a single
 * call site here may toggle chapters from several different folders (e.g.
 * a folder's stale-chapters list only ever lists chapters within itself, so
 * this is mostly one-folder-at-a-time in practice, but genuinely needed for
 * the sidebar tree, which renders one FolderTreeNode per folder). */
export function useToggleChapterComplete() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { chapterId: string; folderId: string; completed: boolean }) =>
      api.patch<ChapterDetail>(`/chapters/${vars.chapterId}`, { completed: vars.completed }),
    onSuccess: (updated, vars) => {
      qc.setQueryData(['chapter', updated.id], updated)
      qc.invalidateQueries({ queryKey: ['folder', vars.folderId] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['goals'] })
    },
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<UserSettings>) => api.patch<UserSettings>('/me/settings', data),
    onSuccess: (updated) => qc.setQueryData(['settings'], updated),
  })
}

/** Un-hides every sub-folder and chapter nested under a folder that was
 * individually closed from the sidebar. Fetches the folder's full subtree
 * of ids, then strips them all from the current user's closed-id lists. */
export function useOpenAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (folderId: string) => {
      const { folderIds, chapterIds } = await api.get<FolderTreeIds>(`/folders/${folderId}/tree-ids`)
      const settings = qc.getQueryData<UserSettings>(['settings'])
      const closedFolderIds = (settings?.closedFolderIds ?? []).filter((id) => !folderIds.includes(id))
      const closedChapterIds = (settings?.closedChapterIds ?? []).filter((id) => !chapterIds.includes(id))
      return api.patch<UserSettings>('/me/settings', { closedFolderIds, closedChapterIds })
    },
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

export function useReorderFolderChildren(folderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { type: 'folder' | 'chapter'; order: string[] }) =>
      api.post<void>(`/folders/${folderId}/reorder`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['folder', folderId] }),
  })
}

export function useReorderBooks() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (order: string[]) => api.patch<UserSettings>('/me/settings', { bookOrder: order }),
    onSuccess: (updated) => {
      qc.setQueryData(['settings'], updated)
      qc.invalidateQueries({ queryKey: ['books'] })
    },
  })
}

export function useAddShare(resourceType: ShareResourceType, resourceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { username: string; role: 'editor' | 'viewer' }) =>
      api.post<Share>(`/${resourceType}s/${resourceId}/shares`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shares', resourceType, resourceId] }),
  })
}

export function useUpdateShare(resourceType: ShareResourceType, resourceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { userId: string; role: 'editor' | 'viewer' }) =>
      api.patch<Share>(`/${resourceType}s/${resourceId}/shares/${data.userId}`, { role: data.role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shares', resourceType, resourceId] }),
  })
}

export function useRemoveShare(resourceType: ShareResourceType, resourceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => api.del<void>(`/${resourceType}s/${resourceId}/shares/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shares', resourceType, resourceId] })
      // Covers self-revoke (leaving a share): the item this was scoped to
      // may need to disappear from the current user's own sidebar.
      qc.invalidateQueries({ queryKey: ['shared-with-me'] })
    },
  })
}

export function useCreateGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      resourceType: GoalResourceType
      resourceId: string
      goalType: GoalType
      target: number
      cadence?: GoalCadence
      startDate?: string
      endDate?: string
      name?: string
    }) => api.post<Goal>('/goals', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  })
}

export function useUpdateGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { goalId: string; target?: number; startDate?: string; endDate?: string; name?: string }) =>
      api.patch<Goal>(`/goals/${vars.goalId}`, {
        target: vars.target,
        startDate: vars.startDate,
        endDate: vars.endDate,
        name: vars.name,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  })
}

export function useDeleteGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (goalId: string) => api.del<void>(`/goals/${goalId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  })
}
