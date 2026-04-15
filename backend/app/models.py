"""Pydantic models for IoT Gateway Simulator.

Supports two connection modes:
- Mode A (mosquitto_via_nginx): Via Mosquitto + Nginx — realistic field gateway flow
- Mode B (tb_direct): Direct to ThingsBoard PE — for testing/debugging
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Connection Modes ───────────────────────────────────────────────


class TransportMode(str, Enum):
    MOSQUITTO_VIA_NGINX = "mosquitto_via_nginx"  # Mode A: realistic
    TB_DIRECT = "tb_direct"  # Mode B: direct to TB PE


class MqttProtocol(str, Enum):
    WEBSOCKETS = "websockets"  # Through Nginx on port 443
    TCP = "tcp"  # Direct MQTT (internal only)


class ScheduleMode(str, Enum):
    DURATION = "duration"
    INFINITE = "infinite"


class SimulationStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


# ─── Transport Configuration ────────────────────────────────────────


class MosquittoViaNginxConfig(BaseModel):
    """Mode A: Connect through Nginx to Mosquitto — realistic field gateway."""

    mqtt_host: str = Field(
        default="gw-lora-0001.iberdrola-arenales-26.sentinels.pro",
        description="Nginx hostname that proxies to Mosquitto",
    )
    mqtt_port: int = Field(default=443, description="Nginx TLS port")
    mqtt_use_tls: bool = Field(default=True, description="TLS required on port 443")
    mqtt_websocket_path: str = Field(
        default="/mqtt", description="WebSocket upgrade path"
    )
    mqtt_protocol: MqttProtocol = Field(default=MqttProtocol.WEBSOCKETS)
    client_id: str = Field(
        default="gw-simulator-001",
        description="ClientID for Mosquitto (anonymous auth)",
    )
    mqtt_username: str = Field(default="", description="Empty = anonymous auth")
    mqtt_password: str = Field(default="", description="Empty = anonymous auth")
    mosquitto_topic: str = Field(
        default="gw-lora-0001/bme680",
        description="Topic to publish on Mosquitto (e.g. gw-lora-0001/bme680)",
    )


class TbDirectConfig(BaseModel):
    """Mode B: Direct MQTT connection to ThingsBoard PE."""

    tb_host: str = Field(
        default="aiot.sentinels.pro",
        description="ThingsBoard PE hostname",
    )
    tb_port: int = Field(default=443, description="TB PE TLS port")
    tb_use_tls: bool = Field(default=True)
    tb_token: str = Field(
        default="",
        description="Access token (env: IBERDROLA_GATEWAY_TOKEN)",
    )
    tb_topic: str = Field(
        default="v1/gateway/telemetry",
        description="TB gateway telemetry topic",
    )


class TransportConfig(BaseModel):
    """Transport configuration — selects Mode A or B."""

    mode: TransportMode = Field(default=TransportMode.MOSQUITTO_VIA_NGINX)
    mosquitto: MosquittoViaNginxConfig = Field(default_factory=MosquittoViaNginxConfig)
    tb_direct: TbDirectConfig = Field(default_factory=TbDirectConfig)


# ─── Gateway & Device Configuration ─────────────────────────────────


class GatewayConfig(BaseModel):
    """Gateway identity in ThingsBoard."""

    name: str = Field(
        default="gw-iot-direct-ingest", description="Gateway device name in TB"
    )
    type: str = Field(default="default", description="Gateway device type")


class DeviceModelConfig(BaseModel):
    """Device model configuration."""

    name: str = Field(default="Nordic")
    perfil: str = Field(default="ULP")
    weight: float = Field(
        default=1.0, description="Probability weight for model selection"
    )


class DeviceConfig(BaseModel):
    """Number and naming of simulated devices."""

    count: int = Field(
        default=10, ge=1, le=500, description="Number of simulated devices"
    )
    prefix: str = Field(default="BME680_SN_", description="Device name prefix")
    serial_prefix: str = Field(
        default="0000000000", description="SerialNumber hex prefix"
    )
    models: list[DeviceModelConfig] = Field(
        default_factory=lambda: [
            DeviceModelConfig(name="Nordic", perfil="ULP", weight=0.8),
            DeviceModelConfig(name="ESP32", perfil="standard", weight=0.2),
        ]
    )


# ─── Telemetry Configuration ────────────────────────────────────────


class TelemetryKeyRange(BaseModel):
    min: float
    max: float
    drift: float = Field(description="Max random walk per tick")


class TelemetryConfig(BaseModel):
    """Telemetry generation configuration."""

    interval_seconds: int = Field(default=30, ge=1, le=3600)
    keys: list[str] = Field(
        default_factory=lambda: [
            "temperature",
            "pressure",
            "humidity",
            "gas_resistance",
            "gas_index",
            "battery_voltage",
        ],
    )
    ranges: dict[str, TelemetryKeyRange] = Field(
        default_factory=lambda: {
            "temperature": TelemetryKeyRange(min=15.0, max=50.0, drift=0.5),
            "pressure": TelemetryKeyRange(min=950.0, max=1050.0, drift=1.0),
            "humidity": TelemetryKeyRange(min=10.0, max=95.0, drift=2.0),
            "gas_resistance": TelemetryKeyRange(
                min=1000.0, max=15000000.0, drift=50000.0
            ),
            "gas_index": TelemetryKeyRange(min=0, max=500, drift=5),
            "battery_voltage": TelemetryKeyRange(min=3.0, max=4.2, drift=0.01),
        }
    )


class ScheduleConfig(BaseModel):
    mode: ScheduleMode = Field(default=ScheduleMode.DURATION)
    duration_minutes: int = Field(
        default=60, description="Duration in minutes (when mode=duration)"
    )


# ─── Full Simulation Profile ────────────────────────────────────────


class SimulationProfile(BaseModel):
    """Complete simulation profile — maps to YAML config files."""

    name: str = Field(..., description="Profile name")
    transport: TransportConfig = Field(default_factory=TransportConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    devices: DeviceConfig = Field(default_factory=DeviceConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)


# ─── Runtime State ────────────────────────────────────────────────────


class SimulationState(BaseModel):
    """Runtime state of a simulation."""

    id: str
    profile: SimulationProfile
    status: SimulationStatus = SimulationStatus.CREATED
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    messages_sent: int = 0
    devices_active: int = 0
    last_telemetry: Optional[dict[str, Any]] = None
    errors: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
