interface Props {
  simId: string
  status: string
  onAction: (action: 'start' | 'stop' | 'pause' | 'resume') => void
  loading: boolean
}

export default function ControlPanel({ simId, status, onAction, loading }: Props) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Controls — {simId}
      </h3>
      <div className="flex gap-2">
        {status === 'created' && (
          <button
            onClick={() => onAction('start')}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            ▶ Start
          </button>
        )}
        {status === 'running' && (
          <>
            <button
              onClick={() => onAction('pause')}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-yellow-500 text-white rounded-md hover:bg-yellow-600 disabled:opacity-50"
            >
              ⏸ Pause
            </button>
            <button
              onClick={() => onAction('stop')}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
            >
              ⏹ Stop
            </button>
          </>
        )}
        {status === 'paused' && (
          <>
            <button
              onClick={() => onAction('resume')}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              ▶ Resume
            </button>
            <button
              onClick={() => onAction('stop')}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
            >
              ⏹ Stop
            </button>
          </>
        )}
        {(status === 'stopped' || status === 'error') && (
          <button
            onClick={() => onAction('start')}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            ▶ Restart
          </button>
        )}
      </div>
    </div>
  )
}