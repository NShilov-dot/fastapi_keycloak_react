import { cn } from '@/lib/utils'

export function LoadingSpinner({ label = 'Loading…', className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn('flex justify-center py-12', className)}>
      <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin" />
      <span className="sr-only">{label}</span>
    </div>
  )
}
