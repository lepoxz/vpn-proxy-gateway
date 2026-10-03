import React, { useState, useEffect, useCallback } from 'react'
import Navbar from './components/Navbar'
import OverviewCards from './components/OverviewCards'
import TunnelList from './components/TunnelList'
import AccountsView from './components/AccountsView'
import EventsView from './components/EventsView'
import CreateTunnelModal from './components/CreateTunnelModal'
import LogsModal from './components/LogsModal'
import TrafficModal from './components/TrafficModal'
import LoginModal from './components/LoginModal'
import Toast from './components/Toast'
import { api } from './api'

export default function App() {
  const [user, setUser] = useState(null)
  const [isLoginOpen, setIsLoginOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('tunnels')

  const [overview, setOverview] = useState(null)
  const [tunnels, setTunnels] = useState([])
  const [accounts, setAccounts] = useState([])
  const [providers, setProviders] = useState([])

  const [isRefreshing, setIsRefreshing] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState(null)

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [logsModalData, setLogsModalData] = useState({ isOpen: false, id: null, name: '' })
  const [trafficModalData, setTrafficModalData] = useState({ isOpen: false, id: null, name: '' })

  // Toast
  const [toast, setToast] = useState({ message: '', type: 'success' })

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => {
      setToast({ message: '', type: 'success' })
    }, 3500)
  }

  // Handle unauthorized event
  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null)
      setIsLoginOpen(true)
    }
    window.addEventListener('vpg-unauthorized', handleUnauthorized)
    return () => window.removeEventListener('vpg-unauthorized', handleUnauthorized)
  }, [])

  // Check auth on start
  useEffect(() => {
    api
      .getMe()
      .then((res) => {
        setUser(res.username)
        setIsLoginOpen(false)
      })
      .catch(() => {
        setIsLoginOpen(true)
      })
  }, [])

  // Refresh all core data
  const loadData = useCallback(async () => {
    if (!user) return
    setIsRefreshing(true)
    try {
      const [ov, tun, acc, prov] = await Promise.all([
        api.getOverview().catch(() => null),
        api.getTunnels().catch(() => []),
        api.getAccounts().catch(() => []),
        api.getProviders().catch(() => []),
      ])
      if (ov) setOverview(ov)
      if (tun) setTunnels(tun)
      if (acc) setAccounts(acc)
      if (prov) setProviders(prov)
    } catch (err) {
      console.error('Failed to load dashboard data', err)
    } finally {
      setIsRefreshing(false)
    }
  }, [user])

  // Initial load and periodic polling
  useEffect(() => {
    if (user) {
      loadData()
      const interval = setInterval(loadData, 12000)
      return () => clearInterval(interval)
    }
  }, [user, loadData])

  // Auth Handlers
  const handleLoginSuccess = (username) => {
    setUser(username)
    setIsLoginOpen(false)
    showToast(`Chào mừng ${username}!`, 'success')
  }

  const handleLogout = async () => {
    try {
      await api.logout()
    } catch {}
    setUser(null)
    setIsLoginOpen(true)
  }

  // Tunnel Actions
  const handleRotate = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await api.rotateTunnel(id)
      setTunnels((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast('Đã bắt đầu xoay sang IP mới!', 'success')
      loadData()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleRestart = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await api.restartTunnel(id)
      setTunnels((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast('Đã khởi động lại container!', 'success')
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleStop = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await api.stopTunnel(id)
      setTunnels((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast('Đã dừng tunnel!', 'info')
      loadData()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleStart = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await api.startTunnel(id)
      setTunnels((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast('Đang kết nối lại tunnel...', 'info')
      loadData()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleCheck = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await api.checkTunnel(id)
      setTunnels((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast(`IP hiện tại: ${updated.current_ip || 'Không phản hồi'}`, 'info')
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Bạn có chắc muốn xóa tunnel "${name}"?`)) return
    setActionLoadingId(id)
    try {
      await api.deleteTunnel(id)
      setTunnels((prev) => prev.filter((t) => t.id !== id))
      showToast(`Đã xóa tunnel ${name}`, 'success')
      loadData()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  return (
    <div className="min-h-full flex flex-col bg-slate-950 text-slate-100">
      {/* Toast */}
      {toast.message && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast({ message: '', type: 'success' })}
        />
      )}

      {/* Login Modal */}
      <LoginModal isOpen={isLoginOpen} onLoginSuccess={handleLoginSuccess} />

      {/* Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onRefresh={loadData}
        isRefreshing={isRefreshing}
        user={user}
        onLogout={handleLogout}
        overview={overview}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Top Overview Cards (shown on all tabs for status monitoring) */}
        <OverviewCards overview={overview} />

        {/* Tab Content */}
        {activeTab === 'tunnels' && (
          <TunnelList
            tunnels={tunnels}
            onRotate={handleRotate}
            onRestart={handleRestart}
            onStop={handleStop}
            onStart={handleStart}
            onCheck={handleCheck}
            onDelete={handleDelete}
            onViewLogs={(id, name) => setLogsModalData({ isOpen: true, id, name })}
            onViewTraffic={(id, name) => setTrafficModalData({ isOpen: true, id, name })}
            onCreateNew={() => setIsCreateModalOpen(true)}
            actionLoadingId={actionLoadingId}
            showToast={showToast}
          />
        )}

        {activeTab === 'accounts' && (
          <AccountsView
            accounts={accounts}
            providers={providers}
            onRefresh={loadData}
            showToast={showToast}
          />
        )}

        {activeTab === 'events' && <EventsView showToast={showToast} />}
      </main>

      {/* Modals */}
      <CreateTunnelModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        accounts={accounts}
        providers={providers}
        onCreated={(newTunnel) => {
          showToast(`Đã tạo tunnel ${newTunnel.name}!`, 'success')
          loadData()
        }}
      />

      <LogsModal
        isOpen={logsModalData.isOpen}
        tunnelId={logsModalData.id}
        tunnelName={logsModalData.name}
        onClose={() => setLogsModalData({ isOpen: false, id: null, name: '' })}
        showToast={showToast}
      />

      <TrafficModal
        isOpen={trafficModalData.isOpen}
        tunnelId={trafficModalData.id}
        tunnelName={trafficModalData.name}
        onClose={() => setTrafficModalData({ isOpen: false, id: null, name: '' })}
        showToast={showToast}
      />
    </div>
  )
}
