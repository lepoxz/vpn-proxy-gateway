import React from 'react'
import { Network, ArrowDownCircle, ArrowUpCircle, ShieldCheck, AlertTriangle } from 'lucide-react'
import { formatBytes } from '../utils'

export default function OverviewCards({ overview }) {
  if (!overview) return null

  const byStatus = overview.by_status || {}
  const healthyCount = byStatus.healthy || 0
  const leakBlocked = byStatus.leak_blocked || 0
  const downCount = (byStatus.down || 0) + (byStatus.error || 0)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* Total Tunnels */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-400">Tunnels Hoạt động</span>
          <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
            <Network className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight text-white">
            {healthyCount}
          </span>
          <span className="text-sm text-slate-400">/ {overview.tunnels_total || 0} tổng cộng</span>
        </div>
        <div className="mt-3 flex items-center gap-2">
          {leakBlocked > 0 ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
              <AlertTriangle className="w-3 h-3" /> {leakBlocked} bị chặn rò rỉ!
            </span>
          ) : downCount > 0 ? (
            <span className="text-xs text-amber-400">{downCount} tunnel mất kết nối</span>
          ) : (
            <span className="text-xs text-emerald-400 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> 100% an toàn không rò rỉ
            </span>
          )}
        </div>
      </div>

      {/* Traffic Download (RX) */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-400">Tải về 24h (Download)</span>
          <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
            <ArrowDownCircle className="w-5 h-5" />
          </div>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white">
          {formatBytes(overview.traffic_24h?.rx_bytes || 0)}
        </div>
        <p className="mt-3 text-xs text-slate-500">Lưu lượng nhận từ VPN về client</p>
      </div>

      {/* Traffic Upload (TX) */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-400">Tải lên 24h (Upload)</span>
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
            <ArrowUpCircle className="w-5 h-5" />
          </div>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white">
          {formatBytes(overview.traffic_24h?.tx_bytes || 0)}
        </div>
        <p className="mt-3 text-xs text-slate-500">Lưu lượng client gửi ra Internet</p>
      </div>

      {/* Accounts & Quota */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-400">VPN Subscriptions</span>
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white">
          {overview.accounts?.length || 0}
        </div>
        <div className="mt-3 text-xs text-slate-400 truncate">
          {overview.accounts && overview.accounts.length > 0 ? (
            <span>
              {overview.accounts.map((a) => `${a.name}: ${a.used}/${a.allowed}`).join(' | ')}
            </span>
          ) : (
            <span className="text-amber-400">Chưa cấu hình tài khoản nào</span>
          )}
        </div>
      </div>
    </div>
  )
}
