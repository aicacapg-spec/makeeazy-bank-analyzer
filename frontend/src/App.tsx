import { Routes, Route, Navigate } from 'react-router-dom'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Upload, History, FileBarChart, Menu, X, ChevronRight, Settings } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/Upload'
import AnalysisPage from './pages/Analysis'
import HistoryPage from './pages/History'
import SettingsPage from './pages/Settings'

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const location = useLocation()
  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload Statement' },
    { path: '/history', icon: History, label: 'History' },
    { path: '/settings', icon: Settings, label: 'AI Settings' },
  ]

  return (
    <>
      <div className={`sidebar-overlay ${open ? 'show' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-logo">
          <div className="logo-icon">M</div>
          <h1>
            MakeEazy
            <span>Bank Analyzer</span>
          </h1>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={onClose}
            >
              <item.icon />
              {item.label}
              {location.pathname === item.path && <ChevronRight style={{ marginLeft: 'auto', width: 14, height: 14 }} />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>MakeEazy v1.0</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>Zero Cost • Self-Hosted</div>
        </div>
      </aside>
    </>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="app-layout">
      <button className="mobile-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/analysis/:clientId" element={<AnalysisPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
