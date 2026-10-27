import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' })
api.interceptors.request.use((config) => { const token = localStorage.getItem('access_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
export const apiError = (error: unknown) => axios.isAxiosError(error) ? (error.response?.data?.detail || 'The request failed. Please try again.') : 'An unexpected error occurred.'
