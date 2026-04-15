"""Simulation engine — manages device pools and telemetry cycles.

Orchestrates SimulatedDevices and MQTT transport lifecycle.
Handles start/stop/pause/resume and provides status reporting.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Union
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
        self.transport: Optional[Union[MosquittoTransport, TbDirectTransport]] = None
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None

    def initialize(self) -> bool:
        """Create device pool and initialize transport."""
        self.devices = create_device_pool(self.profile.devices, self.profile.telemetry)
        self.state.devices_active = len(self.devices)
        logger.info(
            f"[{self.id}] Initialized {len(self.devices)} devices "
            f"for simulation '{self.profile.name}'"
        )

        # Initialize transport based on mode
        if self.profile.transport.mode == TransportMode.MOSQUITTO_VIA_NGINX:
            self.transport = MosquittoTransport(self.profile.transport.mosquitto)
        elif self.profile.transport.mode == TransportMode.TB_DIRECT:
            self.transport = TbDirectTransport(self.profile.transport.tb_direct)
        else:
            logger.error(
                f"[{self.id}] Unknown transport mode: {self.profile.transport.mode}"
            )
            return False

        return True

    async def start(self) -> bool:
        """Connect transport and start telemetry loop."""
        if self._running:
            logger.warning(f"[{self.id}] Simulation already running")
            return False

        if not self.transport:
            if not self.initialize():
                return False

        # Connect transport
        connected = self.transport.connect()
        if not connected:
            # Give it a brief moment — connect() starts loop_start but
            # the on_connect callback needs a moment
            await asyncio.sleep(1.0)
            if not self.transport.connected:
                self.state.status = SimulationStatus.ERROR
                error_msg = "Failed to connect MQTT transport"
                self.state.errors.append(error_msg)
                self._log(error_msg)
                return False

        self._running = True
        self._paused = False
        self.state.status = SimulationStatus.RUNNING
        self.state.started_at = datetime.now(timezone.utc)
        self._log(
            f"Simulation started — {len(self.devices)} devices, interval {self.profile.telemetry.interval_seconds}s"
        )
        logger.info(
            f"[{self.id}] Simulation '{self.profile.name}' started — "
            f"sending telemetry every {self.profile.telemetry.interval_seconds}s"
        )

        # Start telemetry loop
        self._task = asyncio.create_task(self._telemetry_loop())
        return True

    async def stop(self):
        """Stop the simulation and disconnect transport."""
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self.transport:
            self.transport.disconnect()

        self.state.status = SimulationStatus.STOPPED
        self.state.stopped_at = datetime.now(timezone.utc)
        self._log(
            f"Simulation stopped — sent {self.state.messages_sent} messages total"
        )
        logger.info(
            f"[{self.id}] Simulation '{self.profile.name}' stopped — "
            f"sent {self.state.messages_sent} messages"
        )

    async def pause(self):
        """Pause telemetry sending (keep MQTT connection alive)."""
        if not self._running:
            logger.warning(f"[{self.id}] Cannot pause — not running")
            return
        self._running = False
        self._paused = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.state.status = SimulationStatus.PAUSED
        self._log("Simulation paused")
        logger.info(f"[{self.id}] Simulation '{self.profile.name}' paused")

    async def resume(self):
        """Resume paused simulation."""
        if not self._paused:
            logger.warning(f"[{self.id}] Cannot resume — not paused")
            return
        self._running = True
        self._paused = False
        self.state.status = SimulationStatus.RUNNING
        self._task = asyncio.create_task(self._telemetry_loop())
        self._log("Simulation resumed")
        logger.info(f"[{self.id}] Simulation '{self.profile.name}' resumed")

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
                    self._log(
                        f"Duration reached ({self.profile.schedule.duration_minutes}min)"
                    )
                    logger.info(
                        f"[{self.id}] Simulation duration reached "
                        f"({self.profile.schedule.duration_minutes}min)"
                    )
                    await self.stop()
                    return

            await asyncio.sleep(interval)

    def _send_all_devices(self):
        """Send telemetry from all devices based on transport mode."""
        if not self.transport or not self.transport.connected:
            self._log("Transport not connected — skipping telemetry cycle")
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
                    error_msg = f"Failed to publish for device {device.name}"
                    self.state.errors.append(error_msg)
                    self._log(error_msg)

        elif self.profile.transport.mode == TransportMode.TB_DIRECT:
            # Mode B: Bundle all devices in a single gateway telemetry message
            devices_payload: dict[str, list[dict]] = {}
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)

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
                error_msg = "Failed to publish gateway telemetry to TB PE"
                self.state.errors.append(error_msg)
                self._log(error_msg)

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
            "errors": self.state.errors[-10:],
            "last_telemetry_preview": str(self.state.last_telemetry)[:200]
            if self.state.last_telemetry
            else None,
        }

    def _log(self, message: str):
        """Append a timestamped log entry to the simulation state."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.state.logs.append(f"[{timestamp}] {message}")
        # Keep only last 1000 entries to prevent memory bloat
        if len(self.state.logs) > 1000:
            self.state.logs = self.state.logs[-500:]
