import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { taskKeys, tasksApi, type ListTasksParams } from '../api/tasks'
import { STATUS_LABEL, TASK_STATUSES, type TaskStatus } from '../models/task'
import { TaskCard } from '../components/TaskCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

type StatusFilter = TaskStatus | 'all'
type Scope = 'all' | 'mine'

const PAGE_SIZE = 20

// The default data-[state=on]:bg-accent is too faint here (--accent equals --muted).
const ACTIVE_ITEM =
  'data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary'

export default function TasksPage() {
  const [status, setStatus] = useState<StatusFilter>('all')
  const [scope, setScope] = useState<Scope>('all')
  const [page, setPage] = useState(0)

  const params: ListTasksParams = {
    status: status === 'all' ? undefined : status,
    mine: scope === 'mine',
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }
  const { data, isLoading, isError } = useQuery({
    queryKey: taskKeys.list(params),
    queryFn: () => tasksApi.list(params),
    placeholderData: keepPreviousData,
  })

  const tasks = data?.data ?? []
  const totalPages = Math.ceil((data?.meta.total ?? 0) / PAGE_SIZE)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-foreground">Tasks</h1>
        <Button asChild>
          <Link to="/tasks/new">+ New Task</Link>
        </Button>
      </div>

      <ToggleGroup
        type="single"
        value={scope}
        onValueChange={(v) => {
          if (v) {
            setScope(v as Scope)
            setPage(0)
          }
        }}
        variant="outline"
        size="sm"
        aria-label="Filter by scope"
        className="justify-start gap-1 mb-3"
      >
        <ToggleGroupItem value="all" className={ACTIVE_ITEM}>All (organization)</ToggleGroupItem>
        <ToggleGroupItem value="mine" className={ACTIVE_ITEM}>My tasks</ToggleGroupItem>
      </ToggleGroup>

      <ToggleGroup
        type="single"
        value={status}
        onValueChange={(v) => {
          if (v) {
            setStatus(v as StatusFilter)
            setPage(0)
          }
        }}
        variant="outline"
        size="sm"
        aria-label="Filter by status"
        className="justify-start flex-wrap gap-1 mb-5"
      >
        <ToggleGroupItem value="all" className={ACTIVE_ITEM}>All</ToggleGroupItem>
        {TASK_STATUSES.map((s) => (
          <ToggleGroupItem key={s} value={s} className={ACTIVE_ITEM}>
            {STATUS_LABEL[s]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {isLoading && <LoadingSpinner />}

      {isError && (
        <p className="text-red-600 dark:text-red-400 text-sm py-4">Failed to load tasks. Try again.</p>
      )}

      {!isLoading && !isError && tasks.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg mb-2">No tasks here</p>
          <Link to="/tasks/new" className="text-primary text-sm hover:underline">
            Create your first task →
          </Link>
        </div>
      )}

      <div className="grid gap-3">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-6">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </Button>
          <span className="text-sm text-muted-foreground px-2">
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </Button>
        </div>
      )}
    </div>
  )
}
