import { useState, useEffect, useCallback } from 'react'
import {
  simulationsApi,
  profilesApi,
  connectivityApi,
  type SimulationStatus,
  type SimulationDetail,
  type ProfileInfo,
  type ConnectivityResult,
} from './api'
import SimulationCard from './components/SimulationCard'
import ControlPanel from './components/ControlPanel'
import ConnectivityBadge from './components/ConnectivityBadge'
import LogViewer from './components/LogViewer'
import TelemetryPreview from './components/TelemetryPreview'
import DeviceList from './components/DeviceList'
import MetricsBar from './components/MetricsBar'
import ProfileForm from './components/ProfileForm'

type Page = 'dashboard' | 'profiles'

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [sims, setSims] = useState<SimulationStatus[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<SimulationDetail | null>(null)
  const [profiles, setProfiles] = useState<ProfileInfo[]>([])
  const [connectivity, setConnectivity] = useState<ConnectivityResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSims = useCallback(async () => {
    try {
      const data = await simulationsApi.list()
      setSims(data)
    } catch {
      // silently retry
    }
  }, [])

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await profilesApi.list()
      setProfiles(data.profiles)
    } catch {
      // silently retry
    }
  }, [])

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const data = await simulationsApi.get(id)
      setDetail(data)
    } catch {
      // silently retry
    }
  }, [])

  useEffect(() => {
    fetchSims()
    fetchProfiles()
    const interval = setInterval(fetchSims, 5000)
    return () => clearInterval(interval)
  }, [fetchSims, fetchProfiles])

  useEffect(() => {
    if (selected) {
      fetchDetail(selected)
      const interval = setInterval(() => fetchDetail(selected), 3000)
      return () => clearInterval(interval)
    } else {
      setDetail(null)
    }
  }, [selected, fetchDetail])

  const handleAction = async (id: string, action: 'start' | 'stop' | 'pause' | 'resume') => {
    setLoading(true)
    setError(null)
    try {
      await simulationsApi[action](id)
      await fetchSims()
      if (selected === id) await fetchDetail(id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Action failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this simulation?')) return
    setLoading(true)
    setError(null)
    try {
      await simulationsApi.delete(id)
      if (selected === id) setSelected(null)
      await fetchSims()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateFromProfile = async (filename: string) => {
    setLoading(true)
    setError(null)
    try {
      await simulationsApi.create(undefined, filename)
      await fetchSims()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setLoading(false)
    }
  }

  const handleConnectivityCheck = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await connectivityApi.check({
        mode: 'mosquitto_via_nginx',
      })
      setConnectivity(result)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Connectivity check failed')
      setConnectivity(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold text-gray-900">
              IoT Gateway Simulator
            </h1>
            <nav className="flex gap-2">
              <button
                onClick={() => setPage('dashboard')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md ${
                  page === 'dashboard'
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setPage('profiles')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md ${
                  page === 'profiles'
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Profiles
              </button>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <ConnectivityBadge
              result={connectivity}
              onCheck={handleConnectivityCheck}
              loading={loading}
            />
            <span className="text-sm text-gray-500">
              {sims.length} simulation{sims.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">&times;</button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {page === 'dashboard' && (
          <>
            {/* Create simulation */}
            <div className="mb-6 bg-white rounded-lg shadow p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">
                Create Simulation
              </h2>
              <div className="flex flex-wrap gap-2">
                {profiles.map((p) => (
                  <button
                    key={p.filename}
                    onClick={() => handleCreateFromProfile(p.filename)}
                    disabled={loading}
                    className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                  >
                    {p.name} ({p.transport_mode})
                  </button>
                ))}
              </div>
            </div>

            {/* Simulation cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sims.length === 0 ? (
                <div className="col-span-full text-center text-gray-500 py-12">
                  No simulations running. Create one from a profile above.
                </div>
              ) : (
                sims.map((sim) => (
                  <SimulationCard
                    key={sim.id}
                    sim={sim}
                    selected={selected === sim.id}
                    onSelect={() => setSelected(selected === sim.id ? null : sim.id)}
                    onDelete={() => handleDelete(sim.id)}
                  />
                ))
              )}
            </div>

            {/* Detail panel */}
            {detail && selected && (
              <div className="mt-6 space-y-4">
                {/* Control panel */}
                <ControlPanel
                  simId={detail.id}
                  status={detail.status}
                  onAction={(action) => handleAction(detail.id, action)}
                  loading={loading}
                />

                {/* Metrics */}
                <MetricsBar simId={detail.id} status={detail.status} />

                {/* Telemetry preview + Device list */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <TelemetryPreview simId={detail.id} status={detail.status} />
                  <DeviceList devices={detail.devices} />
                </div>

                {/* Log viewer */}
                <LogViewer simId={detail.id} status={detail.status} />
              </div>
            )}
          </>
        )}

        {page === 'profiles' && (
          <ProfileForm
            profiles={profiles}
            onRefresh={fetchProfiles}
            onCreateSim={handleCreateFromProfile}
          />
        )}
      </main>
    </div>
  )
}

export default App