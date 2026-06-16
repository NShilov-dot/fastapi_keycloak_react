import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

export function Header() {
  const { keycloak } = useAuth()
  const username = (keycloak.tokenParsed?.preferred_username as string | undefined)
    ?? (keycloak.tokenParsed?.email as string | undefined)

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/tasks" className="font-semibold text-gray-900 text-lg tracking-tight">
          SaaS Tasks
        </Link>
        <div className="flex items-center gap-4">
          {username && (
            <span className="text-sm text-gray-500">{username}</span>
          )}
          <button
            onClick={() => keycloak.logout({ redirectUri: window.location.origin })}
            className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  )
}
