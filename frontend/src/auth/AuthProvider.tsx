import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import keycloak from './keycloak'

interface AuthContextValue {
  keycloak: typeof keycloak
  ready: boolean
}

const AuthCtx = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady]     = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const initialized           = useRef(false)

  useEffect(() => {
    // Guard against React StrictMode double-invoke
    if (initialized.current) return
    initialized.current = true

    // Set token-refresh handler BEFORE init so it fires even during startup
    keycloak.onTokenExpired = () => {
      keycloak.updateToken(30).catch(() => {
        console.warn('[auth] Silent token refresh failed — logging out')
        keycloak.logout()
      })
    }

    keycloak
      .init({
        onLoad: 'login-required',
        pkceMethod: 'S256',
        checkLoginIframe: false,
      })
      .then(() => setReady(true))
      .catch((err: unknown) => {
        console.error('[auth] Keycloak init failed', err)
        setError('Could not connect to the authentication server. Please try again later.')
      })
  }, [])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-3 max-w-sm px-4">
          <p className="text-gray-700 font-medium">Authentication unavailable</p>
          <p className="text-sm text-gray-500">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-8 h-8 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <AuthCtx.Provider value={{ keycloak, ready }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
