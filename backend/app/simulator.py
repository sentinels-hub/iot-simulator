"""Simulation engine — manages device pools and telemetry cycles."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from .devices import SimulatedDevice, create_device_pool
from .models import (
    SimulationProfile,
    SimulationState,
    SimulationStatus,
    TransportMode,
)
from .transports.mosquitto import MosquittoTransport
from .transports.tb_direct import TbDirectTransport

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Core simulation engine that orchestrates device pools and MQTT transport."""

    def __init__(self, profile: SimulationProfile):
        self.profile = profile
        self.id = str(uuid4())[:8]
        self.state = SimulationState(id=self.id, profile=profile)
        self.devices: list[SimulatedDevice] = []
        self.transport: Optional[MosquittoTransport | TbDirectTransport] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def initialize(self) -> bool:
        """Create device pool and initialize transport."""
        # Create devices
        self.devices = create_device_pool(self.profile.devices, self.profile.telemetry)
        self.state.devices_active = len(self.devices)
        logger.info(
            f"Initialized {len(self.devices)} devices for simulation '{self.profile.name}'"
        )

        # Initialize transport based on mode
        if self.profile.transport.mode == TransportMode.MOSQUITTO_VIA_NGINX:
            self.transport = MosquittoTransport(self.profile.transport.mosquitto)
        elif self.profile.transport.mode == TransportMode.TB_DIRECT:
            self.transport = TbDirectTransport(self.profile.transport.tb_direct)
        else:
            logger.error(f"Unknown transport mode: {self.profile.transport.mode}")
            return False

        return True

    async def start(self) -> bool:
        """Connect transport and start telemetry loop."""
        if self._running:
            logger.warning("Simulation already running")
            return False

        if not self.transport:
            if not self.initialize():
                return False

        # Connect transport
        connected = self.transport.connect()
        if not connected:
            self.state.status = SimulationStatus.ERROR
            self.state.errors.append("Failed to connect MQTT transport")
            return False

        self._running = True
        self.state.status = SimulationStatus.RUNNING
        self.state.started_at = datetime.now(timezone.utc)

        # Start telemetry loop
        self._task = asyncio.create_task(self._telemetry_loop())
        logger.info(
            f"Simulation '{self.profile.name}' started — sending telemetry every {self.profile.telemetry.interval_seconds}s"
        )
        return True

    async def stop(self):
        """Stop the simulation and disconnect transport."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self.transport:
            self.transport.disconnect()

        self.state.status = SimulationStatus.STOPPED
        self.state.stopped_at = datetime.now(timezone.utc)
        logger.info(
            f"Simulation '{self.profile.name}' stopped — sent {self.state.messages_sent} messages"
        )

    async def pause(self):
        """Pause telemetry sending (keep MQTT connection alive)."""
        self._running = False
        self.state.status = SimulationStatus.PAUSED
        logger.info(f"Simulation '{self.profile.name}' paused")

    async def resume(self):
        """Resume paused simulation."""
        self._running = True
        self.state.status = SimulationStatus.RUNNING
        self._task = asyncio.create_task(self._telemetry_loop())
        logger.info(f"Simulation '{self.profile.name}' resumed")

    async def _telemetry_loop(self):
        """Main telemetry sending loop."""
        interval = self.profile.telemetry.interval_seconds
        start_time = time.time()
        duration_seconds = (
            self.profile.schedule.duration_minutes * 60
            if self.profile.schedule.mode.value == "duration"
            else None
        )

        while self._running:
            # Send telemetry from all devices
            self._send_all_devices()

            # Check duration
            if duration_seconds:
                elapsed = time.time() - start_time
                if elapsed >= duration_seconds:
                    logger.info(
                        f"Simulation duration reached ({self.profile.schedule.duration_minutes}min)"
                    )
                    await self.stop()
                    return

            await asyncio.sleep(interval)

    def _send_all_devices(self):
        """Send telemetry from all devices based on transport mode."""
        if not self.transport or not self.transport.connected:
            return

        if self.profile.transport.mode == TransportMode.MOSQUITTO_VIA_NGINX:
            # Mode A: Send each device as individual Mosquitto message
            for device in self.devices:
                payload = device.to_mosquitto_payload()
                success = self.transport.publish(payload)
                if success:
                    self.state.messages_sent += 1
                    self.state.last_telemetry = payload
                else:
                    self.state.errors.append(
                        f"Failed to publish for device {device.name}"
                    )

        elif self.profile.transport.mode == TransportMode.TB_DIRECT:
            # Mode B: Bundle all devices in a single gateway telemetry message
            devices_payload: dict[str, list[dict]] = {}
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)

            gateway_values = {}
            for device in self.devices:
                values = device.to_tb_values()
                devices_payload[device.name] = [{"ts": ts, "values": values}]

            success = self.transport.publish_gateway_telemetry(
                gateway_name=self.profile.gateway.name,
                devices=devices_payload,
            )
            if success:
                self.state.messages_sent += len(self.devices)
                self.state.last_telemetry = devices_payload
            else:
                self.state.errors.append("Failed to publish gateway telemetry to TB PE")

    def get_status(self) -> dict:
        """Get current simulation status."""
        return {
            "id": self.state.id,
            "name": self.profile.name,
            "status": self.state.status.value,
            "transport_mode": self.profile.transport.mode.value,
            "devices_active": self.state.devices_active,
            "messages_sent": self.state.messages_sent,
            "started_at": self.state.started_at.isoformat()
            if self.state.started_at
            else None,
            "stopped_at": self.state.stopped_at.isoformat()
            if self.state.stopped_at
            else None,
            "errors": self.state.errors[-10:],  # Last 10 errors
            "last_telemetry_preview": str(self.state.last_telemetry)[:200]
            if self.state.last_telemetry
            else None,
        }
