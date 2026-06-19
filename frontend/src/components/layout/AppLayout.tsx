import { type ReactNode } from 'react'
import { SidebarProvider, SidebarTrigger } from './sidebar-context'
import { AppSidebar } from './AppSidebar'
import { Toaster } from '@/components/ui/sonner'

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen bg-background">
        <AppSidebar />

        {/* Main column — flex-1 so it rescales as the sidebar width animates */}
        <div className="flex flex-1 flex-col min-w-0">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <SidebarTrigger />
          </header>
          <main className="flex-1 w-full max-w-4xl mx-auto px-4 py-8">
            {children}
          </main>
        </div>
      </div>

      <Toaster />
    </SidebarProvider>
  )
}
