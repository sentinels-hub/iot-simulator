"""Configuration loader — environment settings and YAML profile management.

Reads SIMULATOR_HOST, SIMULATOR_PORT, IBERDROLA_GATEWAY_TOKEN from env.
Scans profiles/ directory for YAML simulation profiles.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from .models import SimulationProfile


class Settings(BaseSettings):
    """Application settings from environment variables and .env file."""

    simulator_host: str = "0.0.0.0"
    simulator_port: int = 8000
    iberdrola_gateway_token: str = ""
    log_level: str = "info"
    profiles_dir: str = "/app/profiles"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()

# Resolve profiles directory relative to project when running locally
PROFILES_DIR = Path(settings.profiles_dir)
if not PROFILES_DIR.is_absolute():
    PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / settings.profiles_dir


def load_profile(filepath: str | Path) -> SimulationProfile:
    """Load and validate a YAML simulation profile.

    Args:
        filepath: Path to the YAML profile file.

    Returns:
        Validated SimulationProfile instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValidationError: If the YAML content does not match the schema.
        yaml.YAMLError: If the YAML is malformed.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Empty profile file: {path}")

    # Override empty TB token with env value
    if "transport" in data and "tb_direct" in data["transport"]:
        if not data["transport"]["tb_direct"].get("tb_token"):
            data["transport"]["tb_direct"]["tb_token"] = (
                settings.iberdrola_gateway_token
            )

    return SimulationProfile(**data)


def list_profiles() -> list[dict]:
    """List all available YAML profiles in the profiles directory.

    Returns:
        List of dicts with name, filename, and path for each profile.
    """
    profiles_path = PROFILES_DIR
    if not profiles_path.exists():
        return []

    results = []
    for f in sorted(profiles_path.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        try:
            profile = load_profile(f)
            results.append(
                {
                    "name": profile.name,
                    "filename": f.name,
                    "path": str(f),
                    "transport_mode": profile.transport.mode.value,
                    "device_count": profile.devices.count,
                }
            )
        except (ValidationError, yaml.YAMLError, ValueError):
            # Skip invalid profiles silently
            continue

    return results


def save_profile(name: str, content: dict) -> SimulationProfile:
    """Validate and save a new simulation profile as YAML.

    Args:
        name: Profile name (used as filename).
        content: Profile data dict matching SimulationProfile schema.

    Returns:
        Validated SimulationProfile instance.

    Raises:
        ValidationError: If content does not match the schema.
    """
    # Override empty TB token with env value
    if "transport" in content and "tb_direct" in content["transport"]:
        if not content["transport"]["tb_direct"].get("tb_token"):
            content["transport"]["tb_direct"]["tb_token"] = (
                settings.iberdrola_gateway_token
            )

    profile = SimulationProfile(**content)

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
    filepath = PROFILES_DIR / f"{safe_name}.yaml"

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(
            profile.model_dump(mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
        )

    return profile
