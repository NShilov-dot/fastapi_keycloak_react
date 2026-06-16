import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, MutationCache, QueryCache } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from './api/client'
import { AuthProvider } from './auth/AuthProvider'
import App from './App'
import './index.css'

function isUnauthorized(err: unknown) {
  return err instanceof ApiError && err.status === 401
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (err) => {
      if (isUnauthorized(err)) {
        // Session expired mid-session; let AuthProvider's onTokenExpired handle it
        console.warn('Query 401 — token refresh should handle this')
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (err) => {
      if (isUnauthorized(err)) {
        console.warn('Mutation 401 — token refresh should handle this')
      }
    },
  }),
  defaultOptions: {
    queries: {
      retry: (failureCount, err) => {
        // Never retry on 4xx client errors
        if (err instanceof ApiError && err.status < 500) return false
        return failureCount < 1
      },
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
