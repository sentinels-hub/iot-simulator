import { useEffect, useRef, useState } from 'react'
import { simulationsApi, createLogStream } from '../api'

interface Props {
  simId: string
  status: string
}

export default function LogViewer({ simId, status }: Props) {
  const [logs, setLogs] = useState<string[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Load initial logs
  useEffect(() => {
    simulationsApi.logs(simId, 50).then((data) => {
      setLogs(data.logs || [])
    }).catch(() => {
      // ignore
    })
  }, [simId])

  // Connect WebSocket when running/paused
  useEffect(() => {
    if (status === 'running' || status === 'paused') {
      try {
        const ws = createLogStream(simId, (msg) => {
          if (msg.type === 'log' && typeof msg.data === 'string') {
            setLogs((prev) => [...prev.slice(-500), msg.data as string])
          }
        })
        wsRef.current = ws
        ws.onopen = () => setWsConnected(true)
        ws.onclose = () => setWsConnected(false)
        ws.onerror = () => setWsConnected(false)
        return () => {
          ws.close()
          wsRef.current = null
        }
      } catch {
        // WebSocket not supported, fall back to polling
      }
    } else {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setWsConnected(false)
    }
  }, [simId, status])

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700">Logs</h3>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
          <span className="text-xs text-gray-500">
            {wsConnected ? 'Live' : 'Polling'}
          </span>
          <button
            onClick={() => setLogs([])}
            className="text-xs text-gray-400 hover:text-gray-600 ml-2"
          >
            Clear
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="log-viewer bg-gray-900 text-green-400 rounded p-3 h-64 overflow-y-auto"
      >
        {logs.length === 0 ? (
          <div className="text-gray-500 text-xs">No logs yet.</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="text-xs leading-relaxed whitespace-pre-wrap">{log}</div>
          ))
        )}
      </div>
    </div>
  )
}