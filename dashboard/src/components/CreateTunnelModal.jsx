import React, { useState, useEffect } from 'react'
import { X, Globe2, Shield, Clock, KeyRound, Loader2, AlertCircle } from 'lucide-react'
import { api } from '../api'

export default function CreateTunnelModal({ isOpen, onClose, accounts, providers, onCreated }) {
  if (!isOpen) return null

  const [name, setName] = useState('')
  const [accountId, setAccountId] = useState('')
  const [protocol, setProtocol] = useState('wireguard')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [rotationMode, setRotationMode] = useState('manual')
  const [rotationInterval, setRotationInterval] = useState(30)
  const [rotationCron, setRotationCron] = useState('')
  const [proxyUser, setProxyUser] = useState('')
  const [proxyPassword, setProxyPassword] = useState('')

  const [locations, setLocations] = useState([])
  const [isLoadingLocations, setIsLoadingLocations] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Selected account object
  const selectedAccount = accounts.find((a) => String(a.id) === String(accountId))
  const selectedProvider = providers.find((p) => p.name === selectedAccount?.provider)

  // Initialize first account if none selected
  useEffect(() => {
    if (!accountId && accounts.length > 0) {
      setAccountId(accounts[0].id)
    }
  }, [accounts, accountId])

  // When selected account changes, update protocols and load locations
  useEffect(() => {
    if (!selectedAccount) return

    // Set default protocol
    const prov = providers.find((p) => p.name === selectedAccount.provider)
    if (prov && prov.protocols.length > 0) {
      setProtocol(prov.protocols[0])
    }

    // Load locations
    setIsLoadingLocations(true)
    api
      .getProviderLocations(selectedAccount.provider)
      .then((data) => {
        setLocations(data)
        if (data.length > 0) {
          setCountry(data[0].country)
          setCity(data[0].cities?.[0] || '')
        }
      })
      .catch((err) => {
        console.error('Failed to load locations', err)
      })
      .finally(() => {
        setIsLoadingLocations(false)
      })
  }, [selectedAccount, providers])

  // When country changes, update city list
  const currentCountryObj = locations.find((l) => l.country === country)
  const availableCities = currentCountryObj?.cities || []

  // Auto suggest name
  useEffect(() => {
    if (country) {
      const sanitizedCountry = country.toLowerCase().replace(/[^a-z0-9]/g, '')
      const sanitizedCity = city ? '-' + city.toLowerCase().replace(/[^a-z0-9]/g, '') : ''
      setName(`proxy-${sanitizedCountry}${sanitizedCity}`)
    }
  }, [country, city])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const payload = {
        name: name.trim(),
        account_id: Number(accountId),
        country,
        city: city || null,
        protocol,
        rotation_mode: rotationMode,
      }

      if (rotationMode === 'interval') {
        payload.rotation_interval_minutes = Number(rotationInterval)
      } else if (rotationMode === 'cron') {
        payload.rotation_cron = rotationCron.trim()
      }

      if (proxyUser.trim()) payload.proxy_user = proxyUser.trim()
      if (proxyPassword.trim()) payload.proxy_password = proxyPassword.trim()

      const created = await api.createTunnel(payload)
      onCreated(created)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <Globe2 className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white">Tạo Tunnel Proxy mới</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 space-y-4 max-h-[75vh] overflow-y-auto pr-1">
          {/* Account */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Tài khoản VPN
            </label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              required
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.provider.toUpperCase()}) — Còn {a.tunnels_allowed - a.tunnels_used} slot
                </option>
              ))}
            </select>
          </div>

          {/* Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Tên Tunnel
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ví dụ: proxy-japan-tokyo"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          {/* Protocol & Location */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Giao thức VPN
              </label>
              <select
                value={protocol}
                onChange={(e) => setProtocol(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                {(selectedProvider?.protocols || ['wireguard', 'openvpn']).map((proto) => (
                  <option key={proto} value={proto}>
                    {proto === 'wireguard' ? 'WireGuard (Nhanh)' : 'OpenVPN'}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Quốc gia
              </label>
              <select
                value={country}
                onChange={(e) => {
                  setCountry(e.target.value)
                  setCity('')
                }}
                disabled={isLoadingLocations}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                required
              >
                {isLoadingLocations ? (
                  <option>Đang tải danh sách...</option>
                ) : (
                  locations.map((l) => (
                    <option key={l.country} value={l.country}>
                      {l.country}
                    </option>
                  ))
                )}
              </select>
            </div>
          </div>

          {/* City */}
          {availableCities.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Thành phố (Tùy chọn)
              </label>
              <select
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">Ngẫu nhiên / Toàn quốc</option>
                {availableCities.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Rotation Policy */}
          <div className="pt-2 border-t border-slate-800/80">
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              <span>Chính sách đổi IP (Rotation)</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'manual', label: 'Thủ công' },
                { id: 'interval', label: 'Theo chu kỳ' },
                { id: 'cron', label: 'Lịch Cron' },
              ].map((m) => (
                <button
                  type="button"
                  key={m.id}
                  onClick={() => setRotationMode(m.id)}
                  className={`py-2 px-3 text-xs font-medium rounded-xl border transition-all ${
                    rotationMode === m.id
                      ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {rotationMode === 'interval' && (
              <div className="mt-3">
                <label className="block text-[11px] text-slate-400 mb-1">
                  Đổi sang IP mới sau mỗi (phút):
                </label>
                <input
                  type="number"
                  min="5"
                  max="43200"
                  value={rotationInterval}
                  onChange={(e) => setRotationInterval(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            {rotationMode === 'cron' && (
              <div className="mt-3">
                <label className="block text-[11px] text-slate-400 mb-1">
                  Biểu thức Cron (giờ UTC):
                </label>
                <input
                  type="text"
                  placeholder="0 */2 * * *"
                  value={rotationCron}
                  onChange={(e) => setRotationCron(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}
          </div>

          {/* Custom Auth (Optional) */}
          <div className="pt-2 border-t border-slate-800/80">
            <span className="block text-[11px] font-semibold text-slate-400 mb-2">
              Tài khoản xác thực Proxy (Để trống sẽ tự sinh ngẫu nhiên an toàn)
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Proxy username"
                value={proxyUser}
                onChange={(e) => setProxyUser(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
              <input
                type="password"
                placeholder="Proxy password"
                value={proxyPassword}
                onChange={(e) => setProxyPassword(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>

          {/* Submit */}
          <div className="pt-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
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
                  <span>Đang khởi tạo container...</span>
                </>
              ) : (
                <span>Tạo Tunnel ngay</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
