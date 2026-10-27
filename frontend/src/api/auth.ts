import { api } from './client'
import type { User } from '../models/user'

export interface LogoutResult {
  status: string
  logout_url: string | null
}

export const authApi = {
  me: () => api.get<User>('/v1/auth/me'),
  logout: () => api.post<LogoutResult>('/v1/auth/logout'),
}
