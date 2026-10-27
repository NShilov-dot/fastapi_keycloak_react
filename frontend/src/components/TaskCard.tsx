import { Link } from 'react-router-dom'
import { PRIORITY_LABEL, isOverdue, type Task, type TaskPriority } from '../models/task'
import { isOwnTask, ownerLabel } from '../models/user'
import { useAuth } from '../auth/AuthProvider'
import { StatusBadge } from './StatusBadge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const PRIORITY_DOT: Record<TaskPriority, string> = {
  low: 'bg-gray-400',
  medium: 'bg-yellow-400',
  high: 'bg-red-500',
}

export function TaskCard({ task }: { task: Task }) {
  const { user } = useAuth()
  const own = isOwnTask(user, task.owner_id)

  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Card className="p-4 shadow-none transition-colors hover:border-primary/50 hover:shadow-md">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium text-foreground truncate">{task.title}</p>
            {task.description && (
              <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{task.description}</p>
            )}
          </div>
          <StatusBadge status={task.status} />
        </div>

        <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className={cn('w-1.5 h-1.5 rounded-full', PRIORITY_DOT[task.priority])} />
            {PRIORITY_LABEL[task.priority]}
          </span>
          {task.due_at && (
            <span className={cn(isOverdue(task) && 'text-red-600 dark:text-red-400 font-medium')}>
              Due {new Date(task.due_at).toLocaleDateString()}
            </span>
          )}
          <span
            className={cn(
              'ml-auto px-1.5 py-0.5 rounded text-[11px]',
              own ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
            )}
            title={own ? 'Your task' : `Owner ${task.owner_id}`}
          >
            {ownerLabel(user, task.owner_id)}
          </span>
        </div>
      </Card>
    </Link>
  )
}
