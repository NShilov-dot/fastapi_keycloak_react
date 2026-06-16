import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { tasksApi } from '../api/tasks'
import type { TaskStatus } from '../types/api'
import { TaskCard } from '../components/TaskCard'
import { LoadingSpinner } from '../components/LoadingSpinner'

const STATUS_TABS: { value: TaskStatus | ''; label: string }[] = [
  { value: '',            label: 'All' },
  { value: 'open',       label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done',       label: 'Done' },
  { value: 'cancelled',  label: 'Cancelled' },
]

const PAGE_SIZE = 20

export default function TasksPage() {
  const [filter, setFilter] = useState<TaskStatus | ''>('')
  const [page, setPage] = useState(0)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['tasks', filter, page],
    queryFn: () =>
      tasksApi.list({
        status: filter || undefined,
        limit:  PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  })

  const tasks      = data?.data ?? []
  const total      = data?.meta.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  function switchFilter(next: TaskStatus | '') {
    setFilter(next)
    setPage(0)
  }

  return (
    <div>
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Tasks</h1>
        <Link
          to="/tasks/new"
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          + New Task
        </Link>
      </div>

      {/* Status tabs */}
      <div className="flex gap-1 mb-5">
        {STATUS_TABS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => switchFilter(value)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              filter === value
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingSpinner />}

      {isError && (
        <p className="text-red-600 text-sm py-4">Failed to load tasks. Try again.</p>
      )}

      {!isLoading && !isError && tasks.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">No tasks here</p>
          <Link
            to="/tasks/new"
            className="text-blue-600 text-sm hover:underline"
          >
            Create your first task →
          </Link>
        </div>
      )}

      <div className="grid gap-3">
        {tasks.map(task => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-6">
          <button
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Prev
          </button>
          <span className="text-sm text-gray-600 px-2">
            {page + 1} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
