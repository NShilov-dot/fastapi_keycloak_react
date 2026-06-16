import { useNavigate, useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi } from '../api/tasks'
import type { TaskStatus } from '../types/api'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingSpinner } from '../components/LoadingSpinner'

const PRIORITY_LABEL = { low: 'Low', medium: 'Medium', high: 'High' } as const

function Btn({
  label,
  onClick,
  disabled,
  variant = 'default',
}: {
  label: string
  onClick: () => void
  disabled: boolean
  variant?: 'default' | 'danger'
}) {
  const base = 'px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed border'
  const cls =
    variant === 'danger'
      ? `${base} border-red-300 text-red-600 hover:bg-red-50`
      : `${base} border-gray-300 text-gray-700 hover:bg-gray-50`
  return (
    <button className={cls} onClick={onClick} disabled={disabled}>
      {label}
    </button>
  )
}

export default function TaskDetailPage() {
  const { id }      = useParams<{ id: string }>()
  const navigate    = useNavigate()
  const qc          = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', id],
    queryFn:  () => tasksApi.get(id!),
    enabled:  !!id,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['tasks'] })

  const startM    = useMutation({ mutationFn: () => tasksApi.start(id!),    onSuccess: invalidate })
  const completeM = useMutation({ mutationFn: () => tasksApi.complete(id!), onSuccess: invalidate })
  const cancelM   = useMutation({ mutationFn: () => tasksApi.cancel(id!),   onSuccess: invalidate })
  const deleteM   = useMutation({
    mutationFn: () => tasksApi.delete(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      navigate('/tasks')
    },
  })

  const busy = startM.isPending || completeM.isPending || cancelM.isPending || deleteM.isPending
  const mutErr = startM.error ?? completeM.error ?? cancelM.error ?? deleteM.error

  if (isLoading) return <LoadingSpinner />

  const task = data?.data
  if (!task) return <p className="text-gray-500 py-8">Task not found.</p>

  const s = task.status as TaskStatus

  return (
    <div className="max-w-lg">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        <Link to="/tasks" className="text-gray-400 hover:text-gray-600">← Tasks</Link>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-4">
          <h1 className="text-xl font-semibold text-gray-900 leading-snug">{task.title}</h1>
          <StatusBadge status={task.status} />
        </div>

        {task.description && (
          <p className="text-gray-600 text-sm mb-5 whitespace-pre-wrap leading-relaxed">
            {task.description}
          </p>
        )}

        {/* Meta grid */}
        <dl className="grid grid-cols-2 gap-y-3 text-sm mb-6">
          <div>
            <dt className="text-gray-400 text-xs uppercase tracking-wide mb-0.5">Priority</dt>
            <dd className="text-gray-900 font-medium">{PRIORITY_LABEL[task.priority]}</dd>
          </div>

          {task.due_at && (
            <div>
              <dt className="text-gray-400 text-xs uppercase tracking-wide mb-0.5">Due</dt>
              <dd className="text-gray-900">{new Date(task.due_at).toLocaleString()}</dd>
            </div>
          )}

          {task.completed_at && (
            <div>
              <dt className="text-gray-400 text-xs uppercase tracking-wide mb-0.5">Completed</dt>
              <dd className="text-gray-900">{new Date(task.completed_at).toLocaleString()}</dd>
            </div>
          )}

          <div>
            <dt className="text-gray-400 text-xs uppercase tracking-wide mb-0.5">Created</dt>
            <dd className="text-gray-900">{new Date(task.created_at).toLocaleDateString()}</dd>
          </div>
        </dl>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-4 border-t border-gray-100">
          {s === 'open' && (
            <Btn label="Start" onClick={() => startM.mutate()} disabled={busy} />
          )}
          {(s === 'open' || s === 'in_progress') && (
            <Btn label="Complete" onClick={() => completeM.mutate()} disabled={busy} />
          )}
          {(s === 'open' || s === 'in_progress') && (
            <Btn label="Cancel" onClick={() => cancelM.mutate()} disabled={busy} />
          )}
          <Btn
            label="Delete"
            variant="danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm('Delete this task?')) deleteM.mutate()
            }}
          />
        </div>

        {mutErr && (
          <p className="text-red-600 text-sm mt-3">Action failed. Please try again.</p>
        )}
      </div>
    </div>
  )
}
