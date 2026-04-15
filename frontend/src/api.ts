import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Types ────────────────────────────────────────────────────────────

export interface SimulationStatus {
  id: string
  name: string
  status: string
  transport_mode: string
  devices_active: number
  messages_sent: number
  started_at: string | null
  stopped_at: string | null
  errors: string[]
  last_telemetry_preview: string | null
}

export interface SimulationDetail extends SimulationStatus {
  devices: DeviceInfo[]
  uptime_seconds: number | null
  errors_count: number
  last_errors: string[]
}

export interface DeviceInfo {
  name: string
  serial_number: string
  model: string
  perfil: string
  cycle: number
}

export interface MetricsData {
  id: string
  status: string
  messages_sent: number
  errors: number
  devices_active: number
  uptime_seconds: number
  msgs_per_sec: number
  remaining_seconds: number | null
}

export interface ProfileInfo {
  name: string
  filename: string
  path: string
  transport_mode: string
  device_count: number
}

export interface ConnectivityResult {
  mode: string
  host: string
  port: number
  success: boolean
  latency_ms: number | null
  error: string | null
}

// ─── API calls ─────────────────────────────────────────────────────────

export const simulationsApi = {
  list: () => api.get<SimulationStatus[]>('/simulations').then(r => r.data),

  get: (id: string) => api.get<SimulationDetail>(`/simulations/${id}`).then(r => r.data),

  create: (body?: Record<string, unknown>, profile?: string) =>
    api.post<SimulationStatus>('/simulations', body, {
      params: profile ? { profile } : undefined,
    }).then(r => r.data),

  start: (id: string) => api.post<SimulationStatus>(`/simulations/${id}/start`).then(r => r.data),

  stop: (id: string) => api.post<SimulationStatus>(`/simulations/${id}/stop`).then(r => r.data),

  pause: (id: string) => api.post<SimulationStatus>(`/simulations/${id}/pause`).then(r => r.data),

  resume: (id: string) => api.post<SimulationStatus>(`/simulations/${id}/resume`).then(r => r.data),

  delete: (id: string) => api.delete(`/simulations/${id}`),

  logs: (id: string, limit = 100) =>
    api.get(`/simulations/${id}/logs`, { params: { limit } }).then(r => r.data),

  metrics: (id: string) => api.get<MetricsData>(`/simulations/${id}/metrics`).then(r => r.data),
}

export const profilesApi = {
  list: () => api.get<{ profiles: ProfileInfo[]; total: number }>('/profiles').then(r => r.data),

  create: (body: Record<string, unknown>) =>
    api.post('/profiles', body).then(r => r.data),
}

export const connectivityApi = {
  check: (body: {
    mode: string
    mosquitto?: Record<string, unknown>
    tb_direct?: Record<string, unknown>
  }) => api.post<ConnectivityResult>('/connectivity/check', body).then(r => r.data),
}

// ─── WebSocket ─────────────────────────────────────────────────────────

export function createLogStream(
  simId: string,
  onMessage: (data: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
): WebSocket {
  const wsBase = API_BASE.replace(/^http/, 'ws').replace(/\/api$/, '')
  const url = `${wsBase}/api/simulations/${simId}/logs/stream`
  const ws = new WebSocket(url)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch {
      // ignore non-JSON messages
    }
  }

  if (onError) {
    ws.onerror = onError
  }

  return ws
}

export default api