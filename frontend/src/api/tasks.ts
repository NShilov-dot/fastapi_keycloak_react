import { api, type Envelope, type PagedEnvelope } from './client'
import type { Task, TaskPriority, TaskStatus } from '../models/task'

export interface ListTasksParams {
  status?: TaskStatus
  limit?: number
  offset?: number
  mine?: boolean
}

export interface CreateTaskInput {
  title: string
  description?: string
  priority?: TaskPriority
  due_at?: string
}

export interface UpdateTaskInput {
  title?: string
  description?: string | null
  priority?: TaskPriority
  due_at?: string | null
}

export const taskKeys = {
  all: ['tasks'] as const,
  lists: () => [...taskKeys.all, 'list'] as const,
  list: (params: ListTasksParams) => [...taskKeys.lists(), params] as const,
  detail: (id: string) => [...taskKeys.all, 'detail', id] as const,
}

const unwrap = (res: Envelope<Task>) => res.data

export const tasksApi = {
  list(params: ListTasksParams = {}) {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.limit !== undefined) qs.set('limit', String(params.limit))
    if (params.offset !== undefined) qs.set('offset', String(params.offset))
    if (params.mine) qs.set('mine', 'true')
    const q = qs.toString() ? `?${qs}` : ''
    return api.get<PagedEnvelope<Task>>(`/v1/tasks${q}`)
  },

  get: (id: string) => api.get<Envelope<Task>>(`/v1/tasks/${id}`).then(unwrap),
  create: (input: CreateTaskInput) => api.post<Envelope<Task>>('/v1/tasks', input).then(unwrap),
  update: (id: string, input: UpdateTaskInput) =>
    api.patch<Envelope<Task>>(`/v1/tasks/${id}`, input).then(unwrap),
  start: (id: string) => api.post<Envelope<Task>>(`/v1/tasks/${id}/start`).then(unwrap),
  complete: (id: string) => api.post<Envelope<Task>>(`/v1/tasks/${id}/complete`).then(unwrap),
  cancel: (id: string) => api.post<Envelope<Task>>(`/v1/tasks/${id}/cancel`).then(unwrap),
  delete: (id: string) => api.delete(`/v1/tasks/${id}`),
}
