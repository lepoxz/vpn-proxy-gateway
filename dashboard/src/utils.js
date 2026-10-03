/**
 * Utility helpers
 */

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export function formatDate(dateString) {
  if (!dateString) return 'Chưa có'
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: '2-digit',
  }).format(date)
}

export function formatRelativeTime(dateString) {
  if (!dateString) return 'Chưa có'
  const date = new Date(dateString)
  const now = new Date()
  const diffSec = Math.floor((now - date) / 1000)

  if (diffSec < 10) return 'Vừa xong'
  if (diffSec < 60) return `${diffSec} giây trước`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`
  return `${Math.floor(diffSec / 86400)} ngày trước`
}

export const STATUS_CONFIG = {
  healthy: {
    label: 'Hoạt động tốt',
    bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-400',
    ping: true,
  },
  connecting: {
    label: 'Đang kết nối',
    bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    dot: 'bg-amber-400',
    ping: true,
  },
  creating: {
    label: 'Đang khởi tạo',
    bg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    dot: 'bg-blue-400',
    ping: true,
  },
  degraded: {
    label: 'Chập chờn',
    bg: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    dot: 'bg-yellow-400',
    ping: false,
  },
  down: {
    label: 'Mất kết nối',
    bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    dot: 'bg-rose-400',
    ping: false,
  },
  leak_blocked: {
    label: 'Chặn rò rỉ IP!',
    bg: 'bg-red-500/20 text-red-300 border-red-500/40',
    dot: 'bg-red-500',
    ping: false,
  },
  stopped: {
    label: 'Đã dừng',
    bg: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    dot: 'bg-slate-400',
    ping: false,
  },
  error: {
    label: 'Lỗi',
    bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    dot: 'bg-rose-400',
    ping: false,
  },
}
