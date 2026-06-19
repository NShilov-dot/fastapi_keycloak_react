import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Button } from '@/components/ui/button'

export function Header() {
  const { user, logout } = useAuth()
  // user.subject is the Keycloak `sub` UUID — show its short form until we
  // wire up a richer /auth/me response (preferred_username, email).
  const label = user.subject.slice(0, 8)

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/tasks" className="font-semibold text-gray-900 text-lg tracking-tight">
          SaaS Tasks
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">{label}</span>
          <Button variant="ghost" size="sm" onClick={logout}>
            Logout
          </Button>
        </div>
      </div>
    </header>
  )
}
