import React, { useState } from 'react'
import { Plus, Users, Trash2, Key, Shield, AlertCircle, Loader2, X } from 'lucide-react'
import { api } from '../api'
import { formatDate } from '../utils'

export default function AccountsView({ accounts, providers, onRefresh, showToast }) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('nordvpn')
  const [credentials, setCredentials] = useState({})
  const [maxDevices, setMaxDevices] = useState(10)
  const [reservedDevices, setReservedDevices] = useState(2)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [modalError, setModalError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const selectedProviderObj = providers.find((p) => p.name === provider) || providers[0]

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider)
    setCredentials({})
    const pObj = providers.find((p) => p.name === newProvider)
    if (pObj) {
      setMaxDevices(pObj.default_max_devices || 10)
    }
  }

  const handleCredentialChange = (field, value) => {
    setCredentials((prev) => ({ ...prev, [field]: value }))
  }

  const handleCreateAccount = async (e) => {
    e.preventDefault()
    setModalError(null)
    setIsSubmitting(true)

    try {
      await api.createAccount({
        name: name.trim(),
        provider,
        credentials,
        max_devices: Number(maxDevices),
        reserved_devices: Number(reservedDevices),
      })
      showToast(`Đã thêm tài khoản ${name}!`, 'success')
      setIsModalOpen(false)
      setName('')
      setCredentials({})
      onRefresh()
    } catch (err) {
      setModalError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (id, accName) => {
    if (!confirm(`Bạn có chắc muốn xóa tài khoản "${accName}"?`)) return
    setDeletingId(id)
    try {
      await api.deleteAccount(id)
      showToast(`Đã xóa tài khoản ${accName}`, 'success')
      onRefresh()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Quản lý Tài khoản VPN</h3>
          <p className="text-xs text-slate-400">
            Quản lý các gói đăng ký VPN trả phí, giới hạn thiết bị (quota) và phân bổ số lượng proxy.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Thêm Tài khoản VPN</span>
        </button>
      </div>

      {/* Accounts Grid */}
      {accounts.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm">
          <Users className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h4 className="text-base font-semibold text-slate-200">Chưa có tài khoản VPN nào</h4>
          <p className="mt-1 text-sm text-slate-400">
            Hãy thêm tài khoản NordVPN, ExpressVPN hoặc các gói VPN khác để bắt đầu tạo proxy.
          </p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition-all"
          >
            <Plus className="w-4 h-4" />
            Thêm tài khoản ngay
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((a) => {
            const usagePercent = Math.round((a.tunnels_used / a.tunnels_allowed) * 100) || 0
            const isNearLimit = a.tunnels_used >= a.tunnels_allowed

            return (
              <div
                key={a.id}
                className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl backdrop-blur-sm flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-sm">
                        {a.provider.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <h4 className="font-bold text-base text-white tracking-tight">{a.name}</h4>
                        <span className="text-xs text-slate-400 uppercase font-semibold">
                          {a.provider}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDelete(a.id, a.name)}
                      disabled={deletingId === a.id || a.tunnels_used > 0}
                      className="p-1.5 hover:bg-rose-950/40 text-slate-500 hover:text-rose-400 rounded-lg transition-colors disabled:opacity-30 disabled:hover:text-slate-500"
                      title={
                        a.tunnels_used > 0
                          ? 'Cần xóa các tunnel thuộc tài khoản này trước'
                          : 'Xóa tài khoản'
                      }
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Device Quota Bar */}
                  <div className="mt-4 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">Số proxy đang dùng:</span>
                      <span className="font-bold text-slate-200">
                        {a.tunnels_used} / {a.tunnels_allowed}{' '}
                        <span className="text-[11px] text-slate-500">
                          (Chừa {a.reserved_devices} slot)
                        </span>
                      </span>
                    </div>

                    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 rounded-full ${
                          isNearLimit ? 'bg-rose-500' : 'bg-indigo-500'
                        }`}
                        style={{ width: `${Math.min(100, usagePercent)}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
                  <span>Tối đa: {a.max_devices} thiết bị</span>
                  <span>{formatDate(a.created_at)}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add Account Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
                  <Shield className="w-5 h-5" />
                </div>
                <h4 className="text-lg font-bold text-white">Thêm Tài khoản VPN</h4>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && (
              <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateAccount} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Tên gợi nhớ tài khoản
                </label>
                <input
                  type="text"
                  placeholder="ví dụ: NordVPN Chính Chủ"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Nhà cung cấp VPN
                </label>
                <select
                  value={provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  {providers.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dynamic Credential Fields */}
              {selectedProviderObj?.credential_fields?.map((field) => (
                <div key={field.name}>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    {field.label}
                  </label>
                  {field.help && (
                    <p className="text-[11px] text-slate-500 mb-1.5">{field.help}</p>
                  )}
                  <input
                    type={field.secret ? 'password' : 'text'}
                    value={credentials[field.name] || ''}
                    onChange={(e) => handleCredentialChange(field.name, e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    required={field.required}
                  />
                </div>
              ))}

              {/* Device Quota Controls */}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Giới hạn thiết bị gói
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={maxDevices}
                    onChange={(e) => setMaxDevices(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Chừa cho thiết bị cá nhân
                  </label>
                  <input
                    type="number"
                    min="0"
                    max={maxDevices - 1}
                    value={reservedDevices}
                    onChange={(e) => setReservedDevices(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                    title="Số slot giữ lại cho điện thoại/laptop của bạn để không bị VPN đá văng"
                  />
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-white"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all active:scale-95 disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang xác thực...</span>
                    </>
                  ) : (
                    <span>Lưu tài khoản</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
