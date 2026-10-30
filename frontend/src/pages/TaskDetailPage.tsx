import { type ReactNode } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import { taskKeys, tasksApi } from '../api/tasks'
import { useAuth } from '../auth/AuthProvider'
import { PRIORITY_LABEL, isActive } from '../models/task'
import { canManageTask, ownerLabel } from '../models/user'
import { getErrorMessage } from '../lib/errors'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

type Transition = 'start' | 'complete' | 'cancel'

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs uppercase tracking-wide mb-0.5">{label}</dt>
      <dd className="text-foreground">{children}</dd>
    </div>
  )
}

export default function TaskDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()

  const { data: task, isLoading, error } = useQuery({
    queryKey: taskKeys.detail(id),
    queryFn: () => tasksApi.get(id),
    enabled: !!id,
  })

  const transition = useMutation({
    mutationFn: (action: Transition) => tasksApi[action](id),
    onSuccess: (updated) => {
      qc.setQueryData(taskKeys.detail(id), updated)
      qc.invalidateQueries({ queryKey: taskKeys.lists() })
    },
    // 404/409 mean the task changed under us: reload the server's state.
    onError: () => qc.invalidateQueries({ queryKey: taskKeys.detail(id) }),
  })

  const remove = useMutation({
    mutationFn: () => tasksApi.delete(id),
    // Leave the detail query alone: navigate() runs in a transition, so this page
    // re-renders once more and would refetch (404) a removed or invalidated query.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: taskKeys.lists() })
      navigate('/tasks', { replace: true })
    },
  })

  if (isLoading) return <LoadingSpinner />
  const gone = error instanceof ApiError && error.status === 404
  if (!task || gone) {
    return (
      <p className="text-muted-foreground py-8">
        {error ? getErrorMessage(error) : 'Task not found.'}
      </p>
    )
  }

  const busy = transition.isPending || remove.isPending
  const active = isActive(task.status)

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-2 mb-6 text-sm">
        <Link to="/tasks" className="text-muted-foreground hover:text-foreground">← Tasks</Link>
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-start justify-between gap-2 mb-4">
          <h1 className="text-xl font-semibold text-foreground leading-snug">{task.title}</h1>
          <StatusBadge status={task.status} />
        </div>

        {task.description && (
          <p className="text-muted-foreground text-sm mb-5 whitespace-pre-wrap leading-relaxed">
            {task.description}
          </p>
        )}

        <dl className="grid grid-cols-2 gap-y-3 text-sm mb-6">
          <Meta label="Owner">
            <span className="font-medium" title={task.owner_id}>{ownerLabel(user, task.owner_id)}</span>
          </Meta>
          <Meta label="Priority">
            <span className="font-medium">{PRIORITY_LABEL[task.priority]}</span>
          </Meta>
          {task.due_at && <Meta label="Due">{new Date(task.due_at).toLocaleString()}</Meta>}
          {task.completed_at && (
            <Meta label="Completed">{new Date(task.completed_at).toLocaleString()}</Meta>
          )}
          <Meta label="Created">{new Date(task.created_at).toLocaleDateString()}</Meta>
        </dl>

        {canManageTask(user, task.owner_id) ? (
          <div className="flex flex-wrap gap-2 pt-4 border-t border-border">
            {task.status === 'open' && (
              <Button variant="outline" size="sm" onClick={() => transition.mutate('start')} disabled={busy}>
                Start
              </Button>
            )}
            {active && (
              <Button variant="outline" size="sm" onClick={() => transition.mutate('complete')} disabled={busy}>
                Complete
              </Button>
            )}
            {active && (
              <Button variant="outline" size="sm" onClick={() => transition.mutate('cancel')} disabled={busy}>
                Cancel
              </Button>
            )}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={busy}>
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this task?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. The task will be permanently removed.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className={buttonVariants({ variant: 'destructive' })}
                    onClick={() => remove.mutate()}
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ) : (
          <p className="pt-4 border-t border-border text-sm text-muted-foreground">
            Read-only — this task belongs to another member of your organization.
          </p>
        )}
      </div>
    </div>
  )
}
