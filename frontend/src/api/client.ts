// BFF client: the browser holds only the HttpOnly session cookie, sent via
// `credentials: 'include'`. A 401 bounces through the backend's OIDC login.
import { redirectToLogin } from '../auth/redirect'

export interface Envelope<T> {
  data: T
}

export interface PagedEnvelope<T> {
  data: T[]
  meta: { total: number; limit: number; offset: number }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API error ${status}`)
    this.name = 'ApiError'
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    // Always set: a non-simple Content-Type forces a CORS preflight on every write.
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    // AuthProvider handles a 401 from /me itself (it owns the loop-breaker UI).
    if (res.status === 401 && path !== '/v1/auth/me') redirectToLogin()
    throw new ApiError(res.status, await res.json().catch(() => null))
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: (path: string) => request<void>('DELETE', path),
}
