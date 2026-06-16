import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import keycloak from './keycloak'

interface AuthContextValue {
  keycloak: typeof keycloak
  ready: boolean
}

const AuthCtx = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const initialized = useRef(false)

  useEffect(() => {
    // Guard against React StrictMode double-invoke
    if (initialized.current) return
    initialized.current = true

    keycloak
      .init({
        onLoad: 'login-required',
        pkceMethod: 'S256',
        checkLoginIframe: false,
      })
      .then(() => setReady(true))
      .catch(console.error)

    keycloak.onTokenExpired = () => {
      keycloak.updateToken(30).catch(() => keycloak.logout())
    }
  }, [])

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
