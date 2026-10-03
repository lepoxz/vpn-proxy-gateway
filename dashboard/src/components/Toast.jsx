import React from 'react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'

export default function Toast({ message, type = 'success', onClose }) {
  if (!message) return null

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    error: <AlertCircle className="w-5 h-5 text-rose-400" />,
    info: <Info className="w-5 h-5 text-indigo-400" />,
  }

  const borderColors = {
    success: 'border-emerald-500/30 bg-slate-900/90 text-emerald-200',
    error: 'border-rose-500/30 bg-slate-900/90 text-rose-200',
    info: 'border-indigo-500/30 bg-slate-900/90 text-indigo-200',
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-5 duration-200">
      <div className={`flex items-center gap-3 ${borderColors[type] || borderColors.info}`}>
        {icons[type] || icons.info}
        <span className="text-sm font-medium">{message}</span>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/10 rounded-lg transition-colors ml-2"
          >
            <X className="w-4 h-4 text-slate-400 hover:text-white" />
          </button>
        )}
      </div>
    </div>
  )
}
