import type { SimulationStatus } from '../api'

interface Props {
  sim: SimulationStatus
  selected: boolean
  onSelect: () => void
  onDelete: () => void
}

const statusColors: Record<string, string> = {
  created: 'bg-gray-100 text-gray-700',
  running: 'bg-green-100 text-green-700',
  paused: 'bg-yellow-100 text-yellow-700',
  stopped: 'bg-red-100 text-red-700',
  error: 'bg-red-200 text-red-800',
}

const modeLabels: Record<string, string> = {
  mosquitto_via_nginx: 'Mode A (Mosquitto)',
  tb_direct: 'Mode B (TB Direct)',
}

export default function SimulationCard({ sim, selected, onSelect, onDelete }: Props) {
  const statusColor = statusColors[sim.status] || 'bg-gray-100 text-gray-700'

  return (
    <div
      className={`bg-white rounded-lg shadow border-2 cursor-pointer transition-all ${
        selected ? 'border-primary-500 ring-2 ring-primary-200' : 'border-transparent hover:border-gray-300'
      }`}
      onClick={onSelect}
    >
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 truncate">{sim.name}</h3>
            <p className="text-xs text-gray-500 mt-0.5">{modeLabels[sim.transport_mode] || sim.transport_mode}</p>
          </div>
          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor}`}>
            {sim.status}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
          <div>
            <span className="text-gray-500">Devices</span>
            <p className="font-medium text-gray-900">{sim.devices_active}</p>
          </div>
          <div>
            <span className="text-gray-500">Messages</span>
            <p className="font-medium text-gray-900">{sim.messages_sent.toLocaleString()}</p>
          </div>
          {sim.started_at && (
            <div className="col-span-2">
              <span className="text-gray-500">Started</span>
              <p className="font-medium text-gray-900 text-xs">
                {new Date(sim.started_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>

        {sim.errors.length > 0 && (
          <div className="mt-2 text-xs text-red-600 truncate">
            ⚠ {sim.errors[sim.errors.length - 1]}
          </div>
        )}

        <div className="mt-3 flex justify-end">
          {sim.status === 'stopped' || sim.status === 'error' ? (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="text-xs text-red-500 hover:text-red-700"
            >
              Delete
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}