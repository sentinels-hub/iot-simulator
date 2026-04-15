"""IoT Gateway Simulator — Backend entry point.

FastAPI application providing:
- REST API for managing simulations (CRUD + start/stop/pause)
- REST API for monitoring simulation status and logs
- Background async tasks for telemetry generation and MQTT transport
- Two connection modes: Mosquitto via Nginx (Mode A) or direct TB PE (Mode B)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="IoT Gateway Simulator",
    version="0.1.0",
    description="Simulates field gateway telemetry to ThingsBoard PE via MQTT/TLS",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "iot-simulator"}


# ─── Simulations ──────────────────────────────────────────────────────


@app.get("/api/simulations")
async def list_simulations():
    """List all simulation profiles and their current status."""
    # TODO: implement with in-memory state store
    return []


@app.post("/api/simulations")
async def create_simulation():
    """Create a new simulation from a profile configuration."""
    # TODO: implement
    return {"id": "TODO", "status": "created"}


@app.get("/api/simulations/{sim_id}")
async def get_simulation(sim_id: str):
    """Get simulation details and current state."""
    # TODO: implement
    return {"id": sim_id, "status": "created"}


@app.post("/api/simulations/{sim_id}/start")
async def start_simulation(sim_id: str):
    """Start a simulation — begins sending telemetry."""
    # TODO: implement — spawn async MQTT tasks
    return {"id": sim_id, "status": "running"}


@app.post("/api/simulations/{sim_id}/stop")
async def stop_simulation(sim_id: str):
    """Stop a running simulation."""
    # TODO: implement — cancel async tasks, disconnect MQTT
    return {"id": sim_id, "status": "stopped"}


@app.post("/api/simulations/{sim_id}/pause")
async def pause_simulation(sim_id: str):
    """Pause a running simulation (can be resumed)."""
    # TODO: implement — suspend telemetry sending, keep MQTT connection
    return {"id": sim_id, "status": "paused"}


# ─── Monitoring ───────────────────────────────────────────────────────


@app.get("/api/simulations/{sim_id}/logs")
async def get_simulation_logs(sim_id: str):
    """Get recent simulation logs."""
    # TODO: implement
    return {"id": sim_id, "logs": []}


@app.get("/api/simulations/{sim_id}/metrics")
async def get_simulation_metrics(sim_id: str):
    """Get simulation metrics (messages sent, errors, device count)."""
    # TODO: implement
    return {"id": sim_id, "messages_sent": 0, "errors": 0, "devices_active": 0}


# ─── Connectivity Check ───────────────────────────────────────────────


@app.post("/api/connectivity/check")
async def check_connectivity():
    """Test MQTT connectivity to target host (Mode A or B)."""
    # TODO: implement — try MQTT connect, report success/failure
    return {"status": "not_implemented"}


# ─── Profiles ──────────────────────────────────────────────────────────


@app.get("/api/profiles")
async def list_profiles():
    """List available simulation profiles YAML."""
    # TODO: implement — scan profiles/ directory
    return []


@app.post("/api/profiles")
async def create_profile():
    """Create a new simulation profile."""
    # TODO: implement — save YAML to profiles/
    return {"status": "not_implemented"}
