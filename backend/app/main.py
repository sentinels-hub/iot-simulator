"""IoT Gateway Simulator — Backend entry point.

FastAPI application providing:
- REST API for managing simulations (CRUD + start/stop/pause)
- REST API for monitoring simulation status and logs
- WebSocket for real-time log streaming
- Background async tasks for telemetry generation and MQTT transport
- Two connection modes: Mosquitto via Nginx (Mode A) or direct TB PE (Mode B)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.connectivity import router as connectivity_router
from .api.monitor import router as monitor_router
from .api.profiles import router as profiles_router
from .api.simulations import router as simulations_router
from .config import settings
from .ws.log_stream import router as log_stream_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

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

# Register routers
app.include_router(simulations_router)
app.include_router(monitor_router)
app.include_router(connectivity_router)
app.include_router(profiles_router)
app.include_router(log_stream_router)


# ─── Health ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "iot-simulator"}
