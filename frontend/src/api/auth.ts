import { api } from './client'

export interface Me {
  subject: string
  tenant_id: string
  roles: string[]
}

export const authApi = {
  me:     ()                 => api.get<Me>('/v1/auth/me'),
  logout: ()                 => api.post<{ status: string }>('/v1/auth/logout'),
}
