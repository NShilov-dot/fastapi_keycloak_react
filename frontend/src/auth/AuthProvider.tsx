import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { authApi } from '../api/auth'
import { ApiError } from '../api/client'
import type { User } from '../models/user'
import { clearRedirectLoopState, redirectToLogin } from './redirect'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Button } from '@/components/ui/button'

interface AuthContextValue {
  user: User
  logout: () => void
}

const AuthCtx = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [error, setError] = useState<string | null>(null)
  // StrictMode runs effects twice in dev; /me must only be requested once.
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    // Set by /v1/auth/callback when Keycloak returned an error; bouncing back to
    // the login would just repeat it.
    const authError = new URLSearchParams(window.location.search).get('auth_error')
    if (authError) {
      // Echo only an OAuth error code, never arbitrary text from a crafted link.
      const code = /^[a-z_]{1,64}$/.test(authError) ? ` (${authError})` : ''
      setError(`Sign-in failed${code}. Please try again.`)
      return
    }

    authApi
      .me()
      .then((me) => {
        clearRedirectLoopState()
        setUser(me)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          if (!redirectToLogin()) {
            setError('Could not establish a session (redirect loop). Please try again later.')
          }
          return
        }
        if (import.meta.env.DEV) console.error('[auth] /auth/me failed', err)
        setError('Could not contact the API. Please try again later.')
      })
  }, [])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-3 max-w-sm px-4">
          <p className="text-foreground font-medium">Something went wrong</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              clearRedirectLoopState()
              window.location.assign('/')
            }}
          >
            Retry
          </Button>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center bg-background">
        <LoadingSpinner className="flex-1" />
      </div>
    )
  }

  const logout = () => {
    authApi
      .logout()
      .then((res) => {
        clearRedirectLoopState()
        // Follow Keycloak's end_session URL so the browser SSO session dies too.
        window.location.assign(res.logout_url || '/')
      })
      .catch(() => window.location.assign('/'))
  }

  return <AuthCtx.Provider value={{ user, logout }}>{children}</AuthCtx.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
