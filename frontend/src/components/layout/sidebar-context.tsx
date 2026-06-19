import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { PanelLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'

type SidebarContextValue = {
  collapsed: boolean
  toggle: () => void
  setCollapsed: (value: boolean) => void
}

const SidebarContext = createContext<SidebarContextValue | null>(null)

export function useSidebar() {
  const ctx = useContext(SidebarContext)
  if (!ctx) throw new Error('useSidebar must be used within <SidebarProvider>')
  return ctx
}

const STORAGE_KEY = 'sidebar:collapsed'

export function SidebarProvider({ children }: { children: ReactNode }) {
  // Initialise from localStorage synchronously so the first paint already has
  // the right width (no collapse flicker on load).
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed))
    } catch {
      /* localStorage unavailable — state stays in-memory only */
    }
  }, [collapsed])

  const toggle = () => setCollapsed((c) => !c)

  return (
    <SidebarContext.Provider value={{ collapsed, toggle, setCollapsed }}>
      {children}
    </SidebarContext.Provider>
  )
}

export function SidebarTrigger() {
  const { collapsed, toggle } = useSidebar()
  const label = collapsed ? 'Expand sidebar' : 'Collapse sidebar'
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      <PanelLeft />
    </Button>
  )
}
