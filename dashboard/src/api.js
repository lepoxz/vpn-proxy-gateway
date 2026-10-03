/**
 * API client for VPN Proxy Gateway
 */

const BASE_URL = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (res.status === 401 && !path.includes('/auth/login')) {
    window.dispatchEvent(new CustomEvent('vpg-unauthorized'))
    throw new Error('Chưa đăng nhập hoặc phiên làm việc đã hết hạn')
  }

  if (!res.ok) {
    let errorMsg = `Lỗi ${res.status}`
    try {
      const data = await res.json()
      errorMsg = data.detail || data.message || errorMsg
    } catch {
      const text = await res.text().catch(() => '')
      if (text) errorMsg = text
    }
    throw new Error(errorMsg)
  }

  if (res.status === 204) return null
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  return res.text()
}

export const api = {
  // Auth
  login: (username, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  getMe: () => request('/api/auth/me'),

  // Overview & Events
  getOverview: () => request('/api/overview'),
  getEvents: (params = {}) => {
    const query = new URLSearchParams()
    if (params.tunnel_id) query.append('tunnel_id', params.tunnel_id)
    if (params.level) query.append('level', params.level)
    if (params.limit) query.append('limit', params.limit)
    return request(`/api/events?${query.toString()}`)
  },

  // Providers
  getProviders: () => request('/api/providers'),
  getProviderLocations: (provider) => request(`/api/providers/${encodeURIComponent(provider)}/locations`),

  // Accounts
  getAccounts: () => request('/api/accounts'),
  createAccount: (data) =>
    request('/api/accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateAccount: (id, data) =>
    request(`/api/accounts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteAccount: (id) =>
    request(`/api/accounts/${id}`, {
      method: 'DELETE',
    }),

  // Tunnels
  getTunnels: () => request('/api/tunnels'),
  getTunnel: (id) => request(`/api/tunnels/${id}`),
  createTunnel: (data) =>
    request('/api/tunnels', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateTunnel: (id, data) =>
    request(`/api/tunnels/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteTunnel: (id) =>
    request(`/api/tunnels/${id}`, {
      method: 'DELETE',
    }),
  rotateTunnel: (id) =>
    request(`/api/tunnels/${id}/rotate`, {
      method: 'POST',
    }),
  restartTunnel: (id) =>
    request(`/api/tunnels/${id}/restart`, {
      method: 'POST',
    }),
  stopTunnel: (id) =>
    request(`/api/tunnels/${id}/stop`, {
      method: 'POST',
    }),
  startTunnel: (id) =>
    request(`/api/tunnels/${id}/start`, {
      method: 'POST',
    }),
  checkTunnel: (id) =>
    request(`/api/tunnels/${id}/check`, {
      method: 'POST',
    }),
  getTunnelTraffic: (id, range = 24) => request(`/api/tunnels/${id}/traffic?range=${range}`),
  getTunnelLogs: (id, tail = 200) => request(`/api/tunnels/${id}/logs?tail=${tail}`),
}
