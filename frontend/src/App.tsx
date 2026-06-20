import { lazy, Suspense } from 'react'
import { Routes, Route, Outlet } from 'react-router-dom'
import { LoadingSpinner } from './components/LoadingSpinner'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppLayout } from './components/layout/AppLayout'
import { AuthProvider } from './auth/AuthProvider'

// Per-route code splitting — each page becomes its own JS chunk
const HomePage       = lazy(() => import('./pages/HomePage'))
const TasksPage      = lazy(() => import('./pages/TasksPage'))
const NewTaskPage    = lazy(() => import('./pages/NewTaskPage'))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'))
const ProfilePage    = lazy(() => import('./pages/ProfilePage'))
const SignupPage     = lazy(() => import('./pages/SignupPage'))

// Authenticated shell: the AuthProvider gate + the app chrome (sidebar/layout).
// Everything nested under it requires a live session; public pages (signup) sit
// OUTSIDE it so they render without bouncing through the OIDC login.
function AuthedShell() {
  return (
    <AuthProvider>
      <AppLayout>
        <Outlet />
      </AppLayout>
    </AuthProvider>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          {/* Public — no session required */}
          <Route path="/signup" element={<SignupPage />} />

          {/* Authenticated app */}
          <Route element={<AuthedShell />}>
            <Route path="/"           element={<HomePage />} />
            <Route path="/tasks"      element={<TasksPage />} />
            <Route path="/tasks/new"  element={<NewTaskPage />} />
            <Route path="/tasks/:id"  element={<TaskDetailPage />} />
            <Route path="/profile"    element={<ProfilePage />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
