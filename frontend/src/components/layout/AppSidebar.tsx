import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import {
  CheckSquare,
  Home,
  ListTodo,
  LogOut,
  Moon,
  Sun,
  User,
  type LucideIcon,
} from 'lucide-react'
import { useTheme } from 'next-themes'
import { useAuth } from '../../auth/AuthProvider'
import { useSidebar } from './sidebar-context'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }

const NAV: NavItem[] = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/profile', label: 'Profile', icon: User },
]

// Shared row styling for nav links and footer action buttons. Collapsed ->
// centre the icon and drop the horizontal padding.
function rowClasses(collapsed: boolean, active: boolean) {
  return cn(
    'flex w-full items-center gap-3 rounded-md h-10 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
    collapsed ? 'justify-center px-0' : 'px-3',
    active
      ? 'bg-primary/10 text-primary'
      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
  )
}

export function AppSidebar() {
  const { collapsed } = useSidebar()
  const { logout } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const isDark = mounted && resolvedTheme === 'dark'

  return (
    <aside
      className={cn(
        'sticky top-0 h-screen shrink-0 overflow-hidden border-r border-border bg-card text-card-foreground flex flex-col transition-[width] duration-200 ease-in-out',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          'flex items-center h-14 shrink-0 border-b border-border',
          collapsed ? 'justify-center px-0' : 'px-4',
        )}
      >
        <Link
          to="/"
          aria-label="SaaS Tasks — home"
          className="flex items-center gap-2 font-semibold tracking-tight text-foreground"
        >
          <CheckSquare className="h-6 w-6 shrink-0 text-primary" />
          {!collapsed && <span className="text-lg">SaaS Tasks</span>}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            aria-label={label}
            title={collapsed ? label : undefined}
            className={({ isActive }) => rowClasses(collapsed, isActive)}
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className={cn('truncate', collapsed && 'sr-only')}>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer: theme toggle + logout */}
      <div className="shrink-0 border-t border-border p-2 space-y-1">
        <button
          type="button"
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          aria-label={isDark ? 'Light mode' : 'Dark mode'}
          title={collapsed ? (isDark ? 'Light mode' : 'Dark mode') : undefined}
          className={rowClasses(collapsed, false)}
        >
          {isDark ? (
            <Sun className="h-5 w-5 shrink-0" />
          ) : (
            <Moon className="h-5 w-5 shrink-0" />
          )}
          <span className={cn('truncate', collapsed && 'sr-only')}>
            {isDark ? 'Light mode' : 'Dark mode'}
          </span>
        </button>

        <button
          type="button"
          onClick={logout}
          aria-label="Logout"
          title={collapsed ? 'Logout' : undefined}
          className={rowClasses(collapsed, false)}
        >
          <LogOut className="h-5 w-5 shrink-0" />
          <span className={cn('truncate', collapsed && 'sr-only')}>Logout</span>
        </button>
      </div>
    </aside>
  )
}
