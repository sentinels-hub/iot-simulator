"""Profile management endpoints — list and create YAML profiles."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..config import list_profiles, save_profile
from ..models import SimulationProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
async def get_profiles():
    """List all available simulation YAML profiles."""
    profiles = list_profiles()
    return {"profiles": profiles, "total": len(profiles)}


@router.post("", status_code=201)
async def create_profile(body: dict):
    """Create a new simulation profile from a JSON body.

    Validates against SimulationProfile schema and saves as YAML.
    """
    try:
        profile = save_profile(body.get("name", "unnamed"), body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    except Exception as exc:
        logger.error(f"Failed to save profile: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {exc}")

    return {
        "name": profile.name,
        "transport_mode": profile.transport.mode.value,
        "device_count": profile.devices.count,
        "status": "created",
    }
