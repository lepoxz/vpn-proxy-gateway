import React, { useState, useEffect } from 'react'
import { X, Terminal, RefreshCw, Copy, Check, Loader2 } from 'lucide-react'
import { api } from '../api'

export default function LogsModal({ isOpen, onClose, tunnelId, tunnelName, showToast }) {
  if (!isOpen) return null

  const [logs, setLogs] = useState('')
  const [tail, setTail] = useState(200)
  const [isLoading, setIsLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const fetchLogs = async () => {
    if (!tunnelId) return
    setIsLoading(true)
    try {
      const text = await api.getTunnelLogs(tunnelId, tail)
      setLogs(text)
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [tunnelId, tail])

  const copyLogs = () => {
    navigator.clipboard.writeText(logs)
    setCopied(true)
    showToast('Đã copy toàn bộ logs!', 'success')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 flex flex-col h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Logs container: <span className="text-indigo-400 font-mono">{tunnelName}</span>
              </h3>
              <p className="text-xs text-slate-400">
                Log từ tiến trình Gluetun VPN & Gost Proxy (thông tin nhạy cảm đã tự động che)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={tail}
              onChange={(e) => setTail(Number(e.target.value))}
              className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value={100}>100 dòng cuối</option>
              <option value={200}>200 dòng cuối</option>
              <option value={500}>500 dòng cuối</option>
              <option value={1000}>1000 dòng cuối</option>
            </select>

            <button
              onClick={fetchLogs}
              disabled={isLoading}
              className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors"
              title="Tải lại log"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>

            <button
              onClick={copyLogs}
              className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 transition-colors"
              title="Copy toàn bộ log"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>

            <button
              onClick={onClose}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Box */}
        <div className="mt-4 flex-1 bg-slate-950 rounded-xl p-4 border border-slate-800/80 overflow-y-auto font-mono text-xs text-slate-300 whitespace-pre-wrap selection:bg-indigo-600 selection:text-white">
          {isLoading && !logs ? (
            <div className="h-full flex items-center justify-center text-slate-500 gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
              <span>Đang tải log...</span>
            </div>
          ) : logs ? (
            logs
          ) : (
            <div className="text-slate-500 text-center py-8">Chưa có dòng log nào.</div>
          )}
        </div>
      </div>
    </div>
  )
}
