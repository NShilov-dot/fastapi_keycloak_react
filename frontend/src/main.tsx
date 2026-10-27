import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, MutationCache } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from 'next-themes'
import { toast } from 'sonner'
import { ApiError } from './api/client'
import { getErrorMessage } from './lib/errors'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onError: (err) => {
      // 401 already bounced through the OIDC login in the api client.
      if (err instanceof ApiError && err.status === 401) return
      toast.error(getErrorMessage(err))
    },
  }),
  defaultOptions: {
    queries: {
      retry: (failureCount, err) =>
        !(err instanceof ApiError && err.status < 500) && failureCount < 1,
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
