import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' })
api.interceptors.request.use((config) => { const token = localStorage.getItem('access_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !['/login', '/register'].includes(error.config?.url || '')) {
      localStorage.removeItem('access_token')
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)
export const apiError = (error: unknown) => axios.isAxiosError(error) ? (error.response?.data?.detail || 'The request failed. Please try again.') : 'An unexpected error occurred.'
