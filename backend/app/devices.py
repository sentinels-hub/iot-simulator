"""Device factory — generates simulated Wingman BSEC devices.

Creates devices with realistic telemetry drift based on BSEC output ranges.
Each device maintains state between ticks for gradual, realistic variation.
"""

import random
import uuid
from datetime import datetime, timezone

from .models import DeviceConfig, DeviceModelConfig, TelemetryConfig, TelemetryKeyRange


# BSEC realistic value ranges per telemetry key
BSEC_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (15.0, 50.0),  # °C ambient
    "pressure": (950.0, 1050.0),  # hPa
    "humidity": (10.0, 95.0),  # %RH
    "gas_resistance": (1000.0, 15000000.0),  # Ω — huge range
    "gas_index": (0, 500),  # IAQ index
    "battery_voltage": (3.0, 4.2),  # V
}

# Per-key drift (max random walk per tick)
BSEC_DRIFT: dict[str, float] = {
    "temperature": 0.5,  # ±0.5°C
    "pressure": 1.0,  # ±1 hPa
    "humidity": 2.0,  # ±2%RH
    "gas_resistance": 50000.0,  # ±50kΩ (wide range)
    "gas_index": 5,  # ±5 IAQ
    "battery_voltage": 0.01,  # ±0.01V (slow drain)
}


class SimulatedDevice:
    """A single simulated Wingman device with persistent state.

    Maintains current sensor values and applies realistic drift per tick.
    Generates BSEC-compatible telemetry payloads in both Mosquitto and
    ThingsBoard gateway formats.
    """

    def __init__(
        self,
        index: int,
        config: DeviceConfig,
        telemetry_config: TelemetryConfig,
    ):
        self.index = index
        self.name = f"{config.prefix}{index:03d}"
        self.serial_number = f"{config.serial_prefix}{index:X}"
        self.telemetry_keys = telemetry_config.keys
        self.ranges = telemetry_config.ranges
        self.cycle = random.randint(1, 100)  # Start at random cycle

        # Pick device model based on weights
        self.model = self._pick_model(config.models)
        self.perfil = self.model.perfil

        # Initialize with random baseline values using config ranges
        self.current_values: dict[str, float] = {}
        for key in self.telemetry_keys:
            if key in self.ranges:
                r = self.ranges[key]
                self.current_values[key] = round(random.uniform(r.min, r.max), 2)
            elif key in BSEC_RANGES:
                low, high = BSEC_RANGES[key]
                self.current_values[key] = round(random.uniform(low, high), 2)

        # Battery starts near full and drains slowly
        if "battery_voltage" in self.current_values:
            self.current_values["battery_voltage"] = round(random.uniform(3.8, 4.2), 2)

    def _pick_model(self, models: list[DeviceModelConfig]) -> DeviceModelConfig:
        """Pick a device model based on weighted probability."""
        if not models:
            return DeviceModelConfig()
        total = sum(m.weight for m in models)
        r = random.uniform(0, total)
        cumulative = 0
        for model in models:
            cumulative += model.weight
            if r <= cumulative:
                return model
        return models[-1]

    def generate_telemetry(self) -> dict:
        """Generate next telemetry reading with realistic BSEC drift."""
        self.cycle += 1

        for key in self.telemetry_keys:
            current = self.current_values.get(key, 0)
            if key in self.ranges:
                r = self.ranges[key]
                drift = r.drift
                low, high = r.min, r.max
            elif key in BSEC_DRIFT:
                drift = BSEC_DRIFT[key]
                low, high = BSEC_RANGES[key]
            else:
                continue

            # Random walk bounded by realistic range
            new_val = current + random.uniform(-drift, drift)
            new_val = max(low, min(high, new_val))

            # Gas resistance has huge range — use log-scale drift
            if key == "gas_resistance":
                if current > 0:
                    multiplier = 1 + random.uniform(-0.05, 0.05)
                    new_val = current * multiplier
                else:
                    new_val = random.uniform(50000, 500000)

            # Battery slowly drains (never charges in sim)
            if key == "battery_voltage":
                drain = random.uniform(0, 0.005)
                new_val = current - drain
                new_val = max(3.0, new_val)

            self.current_values[key] = round(new_val, 2)

        return dict(self.current_values)

    def to_mosquitto_payload(self) -> dict:
        """Generate Mosquitto payload (Mode A).

        Matches the format consumed by TB Gateway's direct_mqtt.json converter.
        """
        telemetry = self.generate_telemetry()
        return {
            "SerialNumber": self.serial_number,
            "Temperature": telemetry.get("temperature", 0),
            "Pressure": telemetry.get("pressure", 0),
            "Humidity": telemetry.get("humidity", 0),
            "Gas_resist": telemetry.get("gas_resistance", 0),
            "Gas_index": telemetry.get("gas_index", 0),
            "Time_stamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "Voltaje_bateria": telemetry.get("battery_voltage", 0),
            "model": self.model.name,
            "Perfil": self.perfil,
            "Ciclo": self.cycle,
        }

    def to_tb_values(self) -> dict:
        """Generate ThingsBoard values dict (used in Mode B gateway payload)."""
        telemetry = self.generate_telemetry()
        return {
            "temperature": telemetry.get("temperature", 0),
            "pressure": telemetry.get("pressure", 0),
            "humidity": telemetry.get("humidity", 0),
            "gasResistance": telemetry.get("gas_resistance", 0),
            "gasIndex": telemetry.get("gas_index", 0),
            "batteryVoltage": telemetry.get("battery_voltage", 0),
        }

    def __repr__(self) -> str:
        return (
            f"SimulatedDevice(name={self.name}, serial={self.serial_number}, "
            f"model={self.model.name}, perfil={self.perfil})"
        )


def create_device_pool(
    config: DeviceConfig,
    telemetry_config: TelemetryConfig,
) -> list[SimulatedDevice]:
    """Create a pool of N simulated Wingman devices."""
    return [
        SimulatedDevice(index=i, config=config, telemetry_config=telemetry_config)
        for i in range(1, config.count + 1)
    ]
