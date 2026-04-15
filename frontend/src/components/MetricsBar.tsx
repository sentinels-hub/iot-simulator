import { useEffect, useState } from 'react'
import { simulationsApi, type MetricsData } from '../api'

interface Props {
  simId: string
  status: string
}

export default function MetricsBar({ simId, status: _status }: Props) {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)

  useEffect(() => {
    const refresh = () => {
      simulationsApi.metrics(simId).then(setMetrics).catch(() => {})
    }
    refresh()
    const interval = setInterval(refresh, 3000)
    return () => clearInterval(interval)
  }, [simId])

  if (!metrics) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse text-sm text-gray-400">Loading metrics...</div>
      </div>
    )
  }

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    return `${h}h ${m}m ${s}s`
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Metrics</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <span className="text-xs text-gray-500">Messages Sent</span>
          <p className="text-lg font-bold text-gray-900">{metrics.messages_sent.toLocaleString()}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Msg/sec</span>
          <p className="text-lg font-bold text-gray-900">{metrics.msgs_per_sec.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Errors</span>
          <p className={`text-lg font-bold ${metrics.errors > 0 ? 'text-red-600' : 'text-gray-900'}`}>
            {metrics.errors}
          </p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Uptime</span>
          <p className="text-lg font-bold text-gray-900">
            {metrics.uptime_seconds > 0 ? formatUptime(metrics.uptime_seconds) : '—'}
          </p>
        </div>
        {metrics.remaining_seconds !== null && metrics.remaining_seconds > 0 && (
          <div>
            <span className="text-xs text-gray-500">Remaining</span>
            <p className="text-lg font-bold text-blue-600">
              {formatUptime(metrics.remaining_seconds)}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}