import { STATUS_LABEL, type TaskStatus } from '../models/task'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const STATUS_STYLE: Record<TaskStatus, string> = {
  open: 'bg-blue-100 text-blue-700 hover:bg-blue-100 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-950',
  in_progress: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-100 dark:bg-yellow-950 dark:text-yellow-300 dark:hover:bg-yellow-950',
  done: 'bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-950 dark:text-green-300 dark:hover:bg-green-950',
  cancelled: 'bg-gray-100 text-gray-500 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-800',
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <Badge
      variant="secondary"
      className={cn('rounded px-2 py-0.5 font-medium shrink-0 border-transparent', STATUS_STYLE[status])}
    >
      {STATUS_LABEL[status]}
    </Badge>
  )
}
