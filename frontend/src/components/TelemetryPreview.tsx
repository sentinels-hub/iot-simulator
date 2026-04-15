import { useEffect, useRef, useState } from 'react'
import { simulationsApi, createLogStream } from '../api'

interface Props {
  simId: string
  status: string
}

export default function TelemetryPreview({ simId, status }: Props) {
  const [preview, setPreview] = useState<string>('')
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // Fetch initial preview
  useEffect(() => {
    simulationsApi.get(simId).then((data) => {
      if (data.last_telemetry_preview) {
        setPreview(data.last_telemetry_preview)
      }
    }).catch(() => {
      // ignore
    })
  }, [simId])

  // Connect WebSocket for live telemetry updates
  useEffect(() => {
    if (status === 'running' || status === 'paused') {
      try {
        const ws = createLogStream(simId, (msg) => {
          if (msg.type === 'telemetry' && typeof msg.data === 'string') {
            setPreview(msg.data)
          }
        })
        wsRef.current = ws
        ws.onopen = () => setWsConnected(true)
        ws.onclose = () => setWsConnected(false)
        return () => {
          ws.close()
          wsRef.current = null
        }
      } catch {
        // fallback
      }
    } else {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setWsConnected(false)
    }
  }, [simId, status])

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700">Last Telemetry</h3>
        <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
      </div>
      <div className="bg-gray-50 rounded p-3 max-h-64 overflow-auto">
        {preview ? (
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{preview}</pre>
        ) : (
          <p className="text-xs text-gray-400">No telemetry data yet.</p>
        )}
      </div>
    </div>
  )
}