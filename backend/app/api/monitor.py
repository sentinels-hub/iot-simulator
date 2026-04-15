"""Monitoring endpoints — logs and metrics for simulations."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..models import SimulationStatus
from .simulations import simulations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["monitoring"])


@router.get("/{sim_id}/logs")
async def get_simulation_logs(sim_id: str, limit: int = 100):
    """Get recent simulation log entries.

    Args:
        sim_id: Simulation ID.
        limit: Maximum number of log entries to return (default 100).
    """
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    logs = engine.state.logs[-limit:]
    return {
        "id": sim_id,
        "count": len(logs),
        "logs": logs,
    }


@router.get("/{sim_id}/metrics")
async def get_simulation_metrics(sim_id: str):
    """Get simulation metrics: messages_sent, errors, uptime, msg/sec."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    uptime_seconds = 0.0
    msgs_per_sec = 0.0
    if engine.state.started_at:
        delta = (datetime.now(timezone.utc) - engine.state.started_at).total_seconds()
        uptime_seconds = round(delta, 1)
        if delta > 0:
            msgs_per_sec = round(engine.state.messages_sent / delta, 4)

    # Remaining time for duration-mode simulations
    remaining_seconds = None
    if (
        engine.state.status == SimulationStatus.RUNNING
        and engine.profile.schedule.mode.value == "duration"
    ):
        duration_secs = engine.profile.schedule.duration_minutes * 60
        if engine.state.started_at:
            elapsed = (
                datetime.now(timezone.utc) - engine.state.started_at
            ).total_seconds()
            remaining_seconds = max(0, round(duration_secs - elapsed, 1))

    return {
        "id": sim_id,
        "status": engine.state.status.value,
        "messages_sent": engine.state.messages_sent,
        "errors": len(engine.state.errors),
        "devices_active": engine.state.devices_active,
        "uptime_seconds": uptime_seconds,
        "msgs_per_sec": msgs_per_sec,
        "remaining_seconds": remaining_seconds,
    }
