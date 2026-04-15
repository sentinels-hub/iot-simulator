import { useState } from 'react'
import { profilesApi, type ProfileInfo } from '../api'

interface Props {
  profiles: ProfileInfo[]
  onRefresh: () => void
  onCreateSim: (filename: string) => void
}

export default function ProfileForm({ profiles, onRefresh, onCreateSim }: Props) {
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [mode, setMode] = useState('mosquitto_via_nginx')
  const [error, setError] = useState<string | null>(null)

  const handleCreate = async () => {
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      await profilesApi.create({
        name: name.trim(),
        transport: { mode },
        devices: { count: 10 },
        telemetry: { interval_seconds: 30 },
        schedule: { mode: 'duration', duration_minutes: 60 },
      })
      setName('')
      onRefresh()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create profile')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Existing profiles */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Available Profiles</h2>
          <button
            onClick={onRefresh}
            className="text-xs text-primary-600 hover:text-primary-700"
          >
            Refresh
          </button>
        </div>

        {profiles.length === 0 ? (
          <p className="text-sm text-gray-400">No profiles found. Create one below.</p>
        ) : (
          <div className="space-y-2">
            {profiles.map((p) => (
              <div key={p.filename} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div>
                  <p className="text-sm font-medium text-gray-900">{p.name}</p>
                  <p className="text-xs text-gray-500">
                    {p.transport_mode} · {p.device_count} devices · {p.filename}
                  </p>
                </div>
                <button
                  onClick={() => onCreateSim(p.filename)}
                  className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
                >
                  Launch
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create new profile */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Create New Profile</h2>

        {error && (
          <div className="mb-3 p-2 text-sm text-red-700 bg-red-50 rounded">{error}</div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Profile Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. my-gateway-sim"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Transport Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="mosquitto_via_nginx">Mode A — Mosquitto via Nginx</option>
              <option value="tb_direct">Mode B — Direct TB PE</option>
            </select>
          </div>

          <button
            onClick={handleCreate}
            disabled={creating || !name.trim()}
            className="w-full px-4 py-2 text-sm font-medium bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            {creating ? 'Creating...' : 'Create Profile'}
          </button>
        </div>
      </div>
    </div>
  )
}