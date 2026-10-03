import React, { useState, useEffect } from 'react'
import { X, BarChart3, ArrowDownCircle, ArrowUpCircle, RefreshCw, Loader2 } from 'lucide-react'
import { api } from '../api'
import { formatBytes, formatDate } from '../utils'

export default function TrafficModal({ isOpen, onClose, tunnelId, tunnelName, showToast }) {
  if (!isOpen) return null

  const [traffic, setTraffic] = useState(null)
  const [range, setRange] = useState(24)
  const [isLoading, setIsLoading] = useState(false)

  const fetchTraffic = async () => {
    if (!tunnelId) return
    setIsLoading(true)
    try {
      const data = await api.getTunnelTraffic(tunnelId, range)
      setTraffic(data)
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchTraffic()
  }, [tunnelId, range])

  const points = traffic?.points || []
  const maxVal = Math.max(...points.map((p) => Math.max(p.rx_bytes, p.tx_bytes)), 1024)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Lưu lượng mạng: <span className="text-indigo-400 font-mono">{tunnelName}</span>
              </h3>
              <p className="text-xs text-slate-400">
                Thống kê băng thông nhận (RX) và gửi (TX) qua proxy
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={range}
              onChange={(e) => setRange(Number(e.target.value))}
              className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value={6}>6 giờ qua</option>
              <option value={24}>24 giờ qua</option>
              <option value={72}>3 ngày qua</option>
              <option value={168}>7 ngày qua</option>
            </select>

            <button
              onClick={fetchTraffic}
              disabled={isLoading}
              className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>

            <button
              onClick={onClose}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        {isLoading && !traffic ? (
          <div className="h-64 flex items-center justify-center text-slate-500 gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
            <span>Đang nạp dữ liệu lưu lượng...</span>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                <div className="flex items-center gap-2 text-cyan-400 mb-1 text-xs font-semibold">
                  <ArrowDownCircle className="w-4 h-4" />
                  <span>Tổng nhận (Download)</span>
                </div>
                <div className="text-xl font-bold text-white">
                  {formatBytes(traffic?.total_rx || 0)}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                <div className="flex items-center gap-2 text-purple-400 mb-1 text-xs font-semibold">
                  <ArrowUpCircle className="w-4 h-4" />
                  <span>Tổng gửi (Upload)</span>
                </div>
                <div className="text-xl font-bold text-white">
                  {formatBytes(traffic?.total_tx || 0)}
                </div>
              </div>
            </div>

            {/* SVG Visual Chart */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="font-semibold text-slate-300">Biểu đồ lưu lượng</span>
                <div className="flex items-center gap-4 text-[11px]">
                  <span className="flex items-center gap-1.5 text-cyan-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" /> Download
                  </span>
                  <span className="flex items-center gap-1.5 text-purple-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400" /> Upload
                  </span>
                </div>
              </div>

              {points.length === 0 ? (
                <div className="h-40 flex items-center justify-center text-xs text-slate-500">
                  Chưa có dữ liệu mẫu lưu lượng nào trong khoảng thời gian này.
                </div>
              ) : (
                <div className="h-44 w-full flex items-end gap-1 pt-6 pb-2">
                  {points.map((p, idx) => {
                    const rxHeight = Math.round((p.rx_bytes / maxVal) * 100) || 2
                    const txHeight = Math.round((p.tx_bytes / maxVal) * 100) || 2

                    return (
                      <div
                        key={idx}
                        className="flex-1 h-full flex items-end gap-0.5 group relative"
                      >
                        <div
                          style={{ height: `${rxHeight}%` }}
                          className="w-full bg-cyan-500/80 rounded-t-sm group-hover:bg-cyan-400 transition-all"
                        />
                        <div
                          style={{ height: `${txHeight}%` }}
                          className="w-full bg-purple-500/80 rounded-t-sm group-hover:bg-purple-400 transition-all"
                        />

                        {/* Tooltip on hover */}
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-20 pointer-events-none p-2 rounded-lg bg-slate-900 border border-slate-700 shadow-xl text-[11px] whitespace-nowrap text-slate-200">
                          <div className="font-semibold text-slate-400">{formatDate(p.ts)}</div>
                          <div className="text-cyan-400">RX: {formatBytes(p.rx_bytes)}</div>
                          <div className="text-purple-400">TX: {formatBytes(p.tx_bytes)}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
