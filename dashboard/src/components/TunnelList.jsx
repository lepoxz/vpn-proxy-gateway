import React, { useState } from 'react'
import {
  RotateCw,
  Play,
  Square,
  RefreshCw,
  Terminal,
  BarChart3,
  Trash2,
  Copy,
  Check,
  Globe2,
  Shield,
  Clock,
  KeyRound,
  Plus,
  Search,
  ExternalLink,
  AlertOctagon,
} from 'lucide-react'
import { STATUS_CONFIG, formatRelativeTime } from '../utils'

export default function TunnelList({
  tunnels,
  onRotate,
  onRestart,
  onStop,
  onStart,
  onCheck,
  onDelete,
  onViewLogs,
  onViewTraffic,
  onCreateNew,
  actionLoadingId,
  showToast,
}) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [copiedKey, setCopiedKey] = useState(null)

  const copyToClipboard = (text, key, label) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    showToast(`Đã copy ${label}!`, 'success')
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const filtered = tunnels.filter((t) => {
    const matchesSearch =
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.country.toLowerCase().includes(search.toLowerCase()) ||
      (t.city && t.city.toLowerCase().includes(search.toLowerCase())) ||
      (t.current_ip && t.current_ip.includes(search)) ||
      (t.account_name && t.account_name.toLowerCase().includes(search.toLowerCase()))

    const matchesStatus = statusFilter === 'all' || t.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <div className="space-y-6">
      {/* Search & Actions Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="flex flex-1 items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Tìm kiếm theo tên, quốc gia, IP..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-900/60 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-slate-900/60 border border-slate-800 rounded-xl text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="healthy">Hoạt động tốt</option>
            <option value="connecting">Đang kết nối</option>
            <option value="down">Mất kết nối</option>
            <option value="leak_blocked">Bị chặn rò rỉ</option>
            <option value="stopped">Đã dừng</option>
          </select>
        </div>

        <button
          onClick={onCreateNew}
          className="flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Tạo Tunnel Proxy mới</span>
        </button>
      </div>

      {/* Empty State */}
      {filtered.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm">
          <Globe2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-200">
            {tunnels.length === 0 ? 'Chưa có Tunnel Proxy nào' : 'Không tìm thấy kết quả phù hợp'}
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            {tunnels.length === 0
              ? 'Tạo tunnel đầu tiên để biến gói VPN của bạn thành proxy SOCKS5/HTTP.'
              : 'Thử tìm với từ khóa hoặc bộ lọc trạng thái khác.'}
          </p>
          {tunnels.length === 0 && (
            <button
              onClick={onCreateNew}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition-all"
            >
              <Plus className="w-4 h-4" />
              Tạo Tunnel ngay
            </button>
          )}
        </div>
      ) : (
        /* Tunnel Cards Grid */
        <div className="grid grid-cols-1 gap-4">
          {filtered.map((t) => {
            const st = STATUS_CONFIG[t.status] || STATUS_CONFIG.error
            const isLoading = actionLoadingId === t.id
            const hostFormat = `${t.proxy.host}:${t.socks_port}:${t.proxy.username}:${t.proxy.password}`

            return (
              <div
                key={t.id}
                className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700/80 transition-all shadow-xl backdrop-blur-sm"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Left Column: Info & Status */}
                  <div className="flex items-start gap-4">
                    {/* Status Dot Pill */}
                    <div className="pt-1">
                      <span
                        className={`relative flex h-3.5 w-3.5`}
                        title={st.label}
                      >
                        {st.ping && (
                          <span
                            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${st.dot}`}
                          />
                        )}
                        <span className={`relative inline-flex rounded-full h-3.5 w-3.5 ${st.dot}`} />
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-base font-bold text-white tracking-tight">{t.name}</h4>
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${st.bg}`}
                        >
                          {st.label}
                        </span>
                        <span className="px-2 py-0.5 text-xs rounded-md bg-slate-800 text-slate-300 font-medium">
                          {t.provider?.toUpperCase()}
                        </span>
                        <span className="px-2 py-0.5 text-xs rounded-md bg-slate-800/60 text-slate-400 font-mono">
                          {t.protocol}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                        <span className="flex items-center gap-1 text-slate-300">
                          <Globe2 className="w-3.5 h-3.5 text-indigo-400" />
                          <strong>{t.country}</strong>
                          {t.city && <span>• {t.city}</span>}
                        </span>

                        <span>
                          Account: <strong className="text-slate-300">{t.account_name || 'N/A'}</strong>
                        </span>

                        {t.rotation_mode !== 'manual' && (
                          <span className="flex items-center gap-1 text-cyan-400">
                            <Clock className="w-3.5 h-3.5" />
                            {t.rotation_mode === 'interval'
                              ? `Xoay mỗi ${t.rotation_interval_minutes}m`
                              : `Cron: ${t.rotation_cron}`}
                          </span>
                        )}

                        <span className="text-slate-500">
                          Kiểm tra: {formatRelativeTime(t.last_check_at)}
                        </span>
                      </div>

                      {t.status_detail && (
                        <p className="text-xs text-rose-400/90 bg-rose-950/30 px-2 py-1 rounded-md border border-rose-900/30 flex items-center gap-1.5 mt-1">
                          <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
                          <span>{t.status_detail}</span>
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Middle Column: Current Public IP & Ports */}
                  <div className="flex flex-wrap items-center gap-3 bg-slate-950/60 px-4 py-2.5 rounded-xl border border-slate-800/80">
                    <div>
                      <span className="block text-[10px] uppercase font-bold text-slate-500">IP Thoát (Egress)</span>
                      <div className="flex items-center gap-1.5 font-mono text-sm font-semibold text-emerald-400">
                        <span>{t.current_ip || 'Đang lấy...'}</span>
                        {t.current_ip && (
                          <button
                            onClick={() => copyToClipboard(t.current_ip, `ip-${t.id}`, 'IP')}
                            className="p-1 hover:text-white text-slate-400 transition-colors"
                            title="Copy IP"
                          >
                            {copiedKey === `ip-${t.id}` ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="h-6 w-px bg-slate-800 hidden sm:block" />

                    <div>
                      <span className="block text-[10px] uppercase font-bold text-slate-500">Ports</span>
                      <div className="font-mono text-xs text-slate-300">
                        <span className="text-indigo-400 font-semibold">SOCKS:</span> {t.socks_port}{' '}
                        <span className="text-slate-600">|</span>{' '}
                        <span className="text-cyan-400 font-semibold">HTTP:</span> {t.http_port}
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Actions */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {/* Rotate IP */}
                    <button
                      onClick={() => onRotate(t.id)}
                      disabled={isLoading || t.status === 'stopped'}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 hover:text-indigo-200 border border-indigo-500/30 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
                      title="Đổi server sang IP mới (giữ nguyên port và user/pass)"
                    >
                      <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                      <span>Đổi IP</span>
                    </button>

                    {/* Check Health */}
                    <button
                      onClick={() => onCheck(t.id)}
                      disabled={isLoading}
                      className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors disabled:opacity-50"
                      title="Kiểm tra kết nối và cập nhật IP"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>

                    {/* Stop / Start */}
                    {t.status === 'stopped' ? (
                      <button
                        onClick={() => onStart(t.id)}
                        disabled={isLoading}
                        className="p-1.5 hover:bg-emerald-950/40 text-emerald-400 rounded-lg border border-slate-800 transition-colors disabled:opacity-50"
                        title="Khởi động lại tunnel"
                      >
                        <Play className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <button
                        onClick={() => onStop(t.id)}
                        disabled={isLoading}
                        className="p-1.5 hover:bg-amber-950/40 text-amber-400 rounded-lg border border-slate-800 transition-colors disabled:opacity-50"
                        title="Dừng tunnel (giải phóng slot thiết bị)"
                      >
                        <Square className="w-3.5 h-3.5" />
                      </button>
                    )}

                    {/* Logs */}
                    <button
                      onClick={() => onViewLogs(t.id, t.name)}
                      className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors"
                      title="Xem log container"
                    >
                      <Terminal className="w-3.5 h-3.5" />
                    </button>

                    {/* Traffic Chart */}
                    <button
                      onClick={() => onViewTraffic(t.id, t.name)}
                      className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors"
                      title="Biểu đồ băng thông"
                    >
                      <BarChart3 className="w-3.5 h-3.5" />
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => onDelete(t.id, t.name)}
                      disabled={isLoading}
                      className="p-1.5 hover:bg-rose-950/30 text-slate-400 hover:text-rose-400 rounded-lg border border-slate-800 transition-colors disabled:opacity-50"
                      title="Xóa tunnel"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Quick Copy Proxy Bar */}
                <div className="mt-4 pt-3 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2 text-slate-400">
                    <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Auth: <strong className="font-mono text-slate-300">{t.proxy.username}</strong> : <strong className="font-mono text-slate-300">{t.proxy.password}</strong></span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => copyToClipboard(t.proxy.socks5_url, `socks-${t.id}`, 'SOCKS5 URL')}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-indigo-300 hover:text-white rounded-md transition-colors"
                    >
                      {copiedKey === `socks-${t.id}` ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>Copy SOCKS5</span>
                    </button>

                    <button
                      onClick={() => copyToClipboard(t.proxy.http_url, `http-${t.id}`, 'HTTP URL')}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-cyan-300 hover:text-white rounded-md transition-colors"
                    >
                      {copiedKey === `http-${t.id}` ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>Copy HTTP</span>
                    </button>

                    <button
                      onClick={() => copyToClipboard(hostFormat, `raw-${t.id}`, 'chuỗi host:port:user:pass')}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white rounded-md transition-colors"
                      title="Format: host:port:user:pass (dùng cho tool/scraper)"
                    >
                      {copiedKey === `raw-${t.id}` ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>host:port:user:pass</span>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
