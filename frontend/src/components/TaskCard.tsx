import { Link } from 'react-router-dom'
import type { Task } from '../types/api'
import { StatusBadge } from './StatusBadge'

const PRIORITY_LABEL = { low: 'Low', medium: 'Med', high: 'High' } as const
const PRIORITY_DOT   = { low: 'bg-gray-400', medium: 'bg-yellow-400', high: 'bg-red-500' } as const

export function TaskCard({ task }: { task: Task }) {
  const due = task.due_at ? new Date(task.due_at) : null
  const overdue =
    due !== null &&
    due < new Date() &&
    task.status !== 'done' &&
    task.status !== 'cancelled'

  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-400 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-gray-900 truncate">{task.title}</p>
          {task.description && (
            <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">{task.description}</p>
          )}
        </div>
        <StatusBadge status={task.status} />
      </div>

      <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${PRIORITY_DOT[task.priority]}`} />
          {PRIORITY_LABEL[task.priority]}
        </span>
        {due && (
          <span className={overdue ? 'text-red-600 font-medium' : ''}>
            Due {due.toLocaleDateString()}
          </span>
        )}
      </div>
    </Link>
  )
}
