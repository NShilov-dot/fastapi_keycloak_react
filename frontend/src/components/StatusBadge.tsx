import type { TaskStatus } from '../types/api'

const STYLES: Record<TaskStatus, string> = {
  open:        'bg-blue-100 text-blue-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  done:        'bg-green-100 text-green-700',
  cancelled:   'bg-gray-100 text-gray-500',
}

const LABELS: Record<TaskStatus, string> = {
  open:        'Open',
  in_progress: 'In Progress',
  done:        'Done',
  cancelled:   'Cancelled',
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium shrink-0 ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  )
}
