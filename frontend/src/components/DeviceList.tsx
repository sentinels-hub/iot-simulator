import type { DeviceInfo } from '../api'

interface Props {
  devices: DeviceInfo[]
}

export default function DeviceList({ devices }: Props) {
  if (!devices || devices.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Devices</h3>
        <p className="text-xs text-gray-400">No devices in this simulation.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Devices ({devices.length})
      </h3>
      <div className="overflow-auto max-h-64">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium text-gray-500">Name</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-500">Serial</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-500">Model</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-500">Profile</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-500">Cycle</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {devices.slice(0, 50).map((d) => (
              <tr key={d.name} className="hover:bg-gray-50">
                <td className="px-2 py-1 text-gray-900">{d.name}</td>
                <td className="px-2 py-1 text-gray-600 font-mono">{d.serial_number}</td>
                <td className="px-2 py-1 text-gray-600">{d.model}</td>
                <td className="px-2 py-1 text-gray-600">{d.perfil}</td>
                <td className="px-2 py-1 text-right text-gray-600">{d.cycle}</td>
              </tr>
            ))}
            {devices.length > 50 && (
              <tr>
                <td colSpan={5} className="px-2 py-1 text-center text-gray-400">
                  ...and {devices.length - 50} more
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}