import { createBrowserRouter, createRoutesFromElements, Route, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import RequireAuth from './components/RequireAuth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import InviteAcceptPage from './pages/InviteAcceptPage'
import InviteAdminPage from './pages/InviteAdminPage'
import HomePage from './pages/HomePage'
import FolderPage from './pages/FolderPage'
import BookSettingsPage from './pages/BookSettingsPage'
import ChapterPage from './pages/ChapterPage'
import SettingsPage from './pages/SettingsPage'
import SearchPage from './pages/SearchPage'
import StatsPage from './pages/StatsPage'
import GoalsPage from './pages/GoalsPage'
import GoalHistoryPage from './pages/GoalHistoryPage'
import ChangelogPage from './pages/ChangelogPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

const router = createBrowserRouter(
  createRoutesFromElements(
    <>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<InviteAcceptPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/goals" element={<GoalsPage />} />
          <Route path="/goals/:goalId/history" element={<GoalHistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/invite" element={<InviteAdminPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/changelog" element={<ChangelogPage />} />
          <Route path="/folders/:folderId" element={<FolderPage />} />
          <Route path="/folders/:folderId/settings" element={<BookSettingsPage />} />
          <Route path="/folders/:folderId/stats" element={<StatsPage />} />
          <Route path="/chapters/:chapterId" element={<ChapterPage />} />
          <Route path="/chapters/:chapterId/stats" element={<StatsPage />} />
        </Route>
      </Route>
    </>,
  ),
)

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  )
}
