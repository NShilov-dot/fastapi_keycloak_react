import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Header } from './components/Header'
import { LoadingSpinner } from './components/LoadingSpinner'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Toaster } from './components/ui/sonner'

// Per-route code splitting — each page becomes its own JS chunk
const TasksPage      = lazy(() => import('./pages/TasksPage'))
const NewTaskPage    = lazy(() => import('./pages/NewTaskPage'))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'))

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <ErrorBoundary>
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              <Route path="/"           element={<Navigate to="/tasks" replace />} />
              <Route path="/tasks"      element={<TasksPage />} />
              <Route path="/tasks/new"  element={<NewTaskPage />} />
              <Route path="/tasks/:id"  element={<TaskDetailPage />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
      <Toaster />
    </div>
  )
}
