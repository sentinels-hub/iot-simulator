import { useState } from 'react'
import type { ConnectivityResult } from '../api'

interface Props {
  result: ConnectivityResult | null
  onCheck: () => void
  loading: boolean
}

export default function ConnectivityBadge({ result, onCheck, loading }: Props) {
  const [showDetail, setShowDetail] = useState(false)

  const getColor = () => {
    if (!result) return 'bg-gray-300'
    if (result.success) return 'bg-green-500'
    return 'bg-red-500'
  }

  const getLabel = () => {
    if (!result) return 'Not tested'
    if (result.success) return `Connected (${result.latency_ms?.toFixed(0)}ms)`
    return `Failed: ${result.error || 'Unknown'}`
  }

  return (
    <div className="relative">
      <button
        onClick={() => {
          onCheck()
          setShowDetail(true)
        }}
        disabled={loading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-50"
      >
        <span className={`w-2 h-2 rounded-full ${getColor()}`} />
        <span className="text-gray-600">
          {loading ? 'Checking...' : getLabel()}
        </span>
      </button>

      {showDetail && result && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 p-3 z-50">
          <div className="flex justify-between items-start mb-2">
            <h4 className="text-sm font-semibold text-gray-900">Connectivity</h4>
            <button onClick={() => setShowDetail(false)} className="text-gray-400 hover:text-gray-600">&times;</button>
          </div>
          <div className="space-y-1 text-xs text-gray-600">
            <div className="flex justify-between">
              <span>Mode</span>
              <span className="font-medium">{result.mode}</span>
            </div>
            <div className="flex justify-between">
              <span>Host</span>
              <span className="font-medium">{result.host}:{result.port}</span>
            </div>
            <div className="flex justify-between">
              <span>Status</span>
              <span className={`font-medium ${result.success ? 'text-green-600' : 'text-red-600'}`}>
                {result.success ? 'Connected' : 'Failed'}
              </span>
            </div>
            {result.latency_ms !== null && (
              <div className="flex justify-between">
                <span>Latency</span>
                <span className="font-medium">{result.latency_ms.toFixed(1)}ms</span>
              </div>
            )}
            {result.error && (
              <div className="mt-1 text-red-600">{result.error}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}