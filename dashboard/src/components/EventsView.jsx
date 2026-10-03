import React, { useState, useEffect } from 'react'
import { Activity, AlertTriangle, AlertCircle, Info, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { formatDate } from '../utils'

export default function EventsView({ showToast }) {
  const [events, setEvents] = useState([])
  const [level, setLevel] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const fetchEvents = async () => {
    setIsLoading(true)
    try {
      const data = await api.getEvents({ level: level || undefined, limit: 100 })
      setEvents(data)
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [level])

  const levelBadges = {
    info: {
      bg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
      icon: <Info className="w-3.5 h-3.5" />,
    },
    warning: {
      bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
    },
    error: {
      bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      icon: <AlertCircle className="w-3.5 h-3.5" />,
    },
  }

  return (
    <div className="space-y-6">
      {/* Header & Filter */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Nhật ký Hoạt động (Events)</h3>
          <p className="text-xs text-slate-400">
            Lịch sử tự động xoay server, cảnh báo rớt mạng, kích hoạt Kill-switch và các thao tác quản trị.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Tất cả mức độ</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>

          <button
            onClick={fetchEvents}
            disabled={isLoading}
            className="p-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-300 hover:text-white transition-colors disabled:opacity-50"
            title="Tải lại nhật ký"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-indigo-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Events Table */}
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 overflow-hidden shadow-xl backdrop-blur-sm">
        {events.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">
            Không có sự kiện nào được ghi nhận.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="text-xs uppercase bg-slate-950/60 text-slate-400 border-b border-slate-800 font-semibold">
                <tr>
                  <th className="px-5 py-3.5">Thời gian</th>
                  <th className="px-5 py-3.5">Mức độ</th>
                  <th className="px-5 py-3.5">Loại</th>
                  <th className="px-5 py-3.5">Nội dung chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                {events.map((ev) => {
                  const badge = levelBadges[ev.level] || levelBadges.info
                  return (
                    <tr key={ev.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-5 py-3 whitespace-nowrap text-slate-400 font-sans text-xs">
                        {formatDate(ev.ts)}
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-sans font-medium border ${badge.bg}`}
                        >
                          {badge.icon}
                          <span className="capitalize">{ev.level}</span>
                        </span>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap text-slate-300 font-semibold">
                        {ev.kind}
                      </td>
                      <td className="px-5 py-3 text-slate-300 font-sans text-xs break-all max-w-xl">
                        {ev.message}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
