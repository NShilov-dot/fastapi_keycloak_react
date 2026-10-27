// Mirrors backend app/models/task.py — keep enums and limits in sync.
export const TASK_STATUSES = ['open', 'in_progress', 'done', 'cancelled'] as const
export const TASK_PRIORITIES = ['low', 'medium', 'high'] as const

export type TaskStatus = (typeof TASK_STATUSES)[number]
export type TaskPriority = (typeof TASK_PRIORITIES)[number]

export const TITLE_MAX = 200
export const DESCRIPTION_MAX = 4000

export interface Task {
  id: string
  owner_id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  due_at: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  open: 'Open',
  in_progress: 'In Progress',
  done: 'Done',
  cancelled: 'Cancelled',
}

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

/** Not yet done or cancelled — can still be completed or cancelled. */
export function isActive(status: TaskStatus): boolean {
  return status === 'open' || status === 'in_progress'
}

export function isOverdue(task: Task, now = new Date()): boolean {
  return task.due_at !== null && isActive(task.status) && new Date(task.due_at) < now
}
