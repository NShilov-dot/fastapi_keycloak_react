import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { LoadingSpinner } from './components/LoadingSpinner'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppLayout } from './components/layout/AppLayout'

// Per-route code splitting — each page becomes its own JS chunk
const HomePage       = lazy(() => import('./pages/HomePage'))
const TasksPage      = lazy(() => import('./pages/TasksPage'))
const NewTaskPage    = lazy(() => import('./pages/NewTaskPage'))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'))
const ProfilePage    = lazy(() => import('./pages/ProfilePage'))

export default function App() {
  return (
    <AppLayout>
      <ErrorBoundary>
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/"           element={<HomePage />} />
            <Route path="/tasks"      element={<TasksPage />} />
            <Route path="/tasks/new"  element={<NewTaskPage />} />
            <Route path="/tasks/:id"  element={<TaskDetailPage />} />
            <Route path="/profile"    element={<ProfilePage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </AppLayout>
  )
}
