import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResultPage } from './pages/ResultPage'
import { ReviewPage } from './pages/ReviewPage'
import { SettingsPage } from './pages/SettingsPage'
import { UploadPage } from './pages/UploadPage'

function Guard({ children }: { children: JSX.Element }) { return localStorage.getItem('access_token') ? children : <Navigate to="/login" replace /> }
function Protected() { return <AppShell><Routes><Route path="/dashboard" element={<DashboardPage />} /><Route path="/upload" element={<UploadPage />} /><Route path="/review" element={<ReviewPage />} /><Route path="/result/:id" element={<ResultPage />} /><Route path="/reports" element={<HistoryPage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></AppShell> }
export default function App() { return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route path="/*" element={<Guard><Protected /></Guard>} /></Routes> }
