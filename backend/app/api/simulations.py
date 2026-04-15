"""Simulation CRUD + lifecycle endpoints.

Create, list, get, start, stop, pause, resume, delete simulations.
All state is held in-memory (no persistent storage needed for a simulator).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..config import load_profile, settings
from ..models import (
    SimulationProfile,
    SimulationState,
    SimulationStatus,
)
from ..simulator import SimulationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# In-memory simulation store
simulations: dict[str, SimulationEngine] = {}


@router.get("", response_model=list[dict])
async def list_simulations():
    """List all simulations with their current status."""
    return [engine.get_status() for engine in simulations.values()]


@router.post("", status_code=201)
async def create_simulation(body: Optional[dict] = None, profile: Optional[str] = None):
    """Create a new simulation from a JSON body or a named YAML profile.

    Accepts either:
    - JSON body with full SimulationProfile fields
    - `profile` query parameter referencing a YAML file in profiles/
    """
    if profile:
        # Load from named YAML profile
        try:
            profile_path = f"{settings.profiles_dir.rstrip('/')}/{profile}"
            if not profile_path.endswith(".yaml"):
                profile_path += ".yaml"
            sim_profile = load_profile(profile_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile}")
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid profile: {exc}")
    elif body:
        # Create from JSON body
        try:
            # Override TB token from env if empty
            transport = body.get("transport", {})
            tb_direct = transport.get("tb_direct", {})
            if not tb_direct.get("tb_token"):
                tb_direct["tb_token"] = settings.iberdrola_gateway_token
                body["transport"]["tb_direct"] = tb_direct
            sim_profile = SimulationProfile(**body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a JSON body or a 'profile' query parameter",
        )

    engine = SimulationEngine(profile=sim_profile)

    # Initialize device pool
    if not engine.initialize():
        raise HTTPException(
            status_code=500, detail="Failed to initialize simulation engine"
        )

    simulations[engine.id] = engine
    logger.info(f"Created simulation '{sim_profile.name}' with id={engine.id}")

    return engine.get_status()


@router.get("/{sim_id}")
async def get_simulation(sim_id: str):
    """Get full simulation detail including devices and metrics."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    status = engine.get_status()

    # Add device details
    devices = []
    for d in engine.devices:
        devices.append(
            {
                "name": d.name,
                "serial_number": d.serial_number,
                "model": d.model.name,
                "perfil": d.perfil,
                "cycle": d.cycle,
            }
        )

    uptime = None
    if engine.state.started_at:
        delta = (datetime.now(timezone.utc) - engine.state.started_at).total_seconds()
        uptime = round(delta, 1)

    return {
        **status,
        "devices": devices,
        "uptime_seconds": uptime,
        "errors_count": len(engine.state.errors),
        "last_errors": engine.state.errors[-10:],
    }


@router.post("/{sim_id}/start")
async def start_simulation(sim_id: str):
    """Start a simulation — connect MQTT and begin telemetry loop."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    if engine.state.status == SimulationStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Simulation already running")

    if engine.state.status == SimulationStatus.PAUSED:
        # Resume a paused sim instead
        raise HTTPException(
            status_code=409,
            detail="Simulation is paused — use /resume instead",
        )

    success = await engine.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start simulation")

    return engine.get_status()


@router.post("/{sim_id}/stop")
async def stop_simulation(sim_id: str):
    """Stop a running or paused simulation."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    if engine.state.status not in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
        raise HTTPException(
            status_code=409, detail="Simulation is not running or paused"
        )

    await engine.stop()
    return engine.get_status()


@router.post("/{sim_id}/pause")
async def pause_simulation(sim_id: str):
    """Pause a running simulation (keeps MQTT alive)."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    if engine.state.status != SimulationStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Simulation is not running")

    await engine.pause()
    return engine.get_status()


@router.post("/{sim_id}/resume")
async def resume_simulation(sim_id: str):
    """Resume a paused simulation."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    if engine.state.status != SimulationStatus.PAUSED:
        raise HTTPException(status_code=409, detail="Simulation is not paused")

    await engine.resume()
    return engine.get_status()


@router.delete("/{sim_id}", status_code=204)
async def delete_simulation(sim_id: str):
    """Remove a simulation (must be stopped first)."""
    engine = simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")

    if engine.state.status in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
        raise HTTPException(
            status_code=409,
            detail="Stop simulation before deleting",
        )

    del simulations[sim_id]
    logger.info(f"Deleted simulation {sim_id}")
