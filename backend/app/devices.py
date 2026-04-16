"""Device factory — generates simulated Wingman BSEC devices.

Creates devices with realistic telemetry drift based on BSEC output ranges
observed from real field devices at Iberdrola Arenales.
Each device maintains state between ticks for gradual, realistic variation.
"""

import random
from datetime import datetime, timezone

from .models import DeviceConfig, DeviceModelConfig, TelemetryConfig, TelemetryKeyRange


# BSEC realistic value ranges — tuned from real Wingman field data (Arenales)
BSEC_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (28.0, 45.0),  # °C — field readings 33-37°C, allow wider
    "pressure": (970.0, 985.0),  # hPa — very stable around 976
    "humidity": (15.0, 35.0),  # %RH — field 20-23%, inverse to temp
    "gas_resistance": (50000.0, 15000000.0),  # Ω — enormous variance
    "gas_index": (0, 500),  # IAQ index — incrementing counter
    "battery_voltage": (3.5, 4.2),  # V — starts near 4.17
}

# Per-key drift — realistic BSEC sensor walk per reading
BSEC_DRIFT: dict[str, float] = {
    "temperature": 0.15,  # ±0.15°C per reading (gradual thermal drift)
    "pressure": 0.02,  # ±0.02 hPa (barometric pressure very stable)
    "humidity": 0.25,  # ±0.25%RH (slow inverse-correlation with temp)
    "gas_resistance": 0.0,  # Handled with log-scale multiplier
    "gas_index": 0,  # Always increments by 1
    "battery_voltage": 0.002,  # ±0.002V (very slow drain)
}


class SimulatedDevice:
    """A single simulated Wingman device with persistent state.

    Maintains current sensor values and applies realistic drift per tick.
    Payload format matches real BSEC field output from Arenales devices.
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
        self.cycle = random.randint(100, 300)  # Start at realistic cycle count

        # Pick device model based on weights
        self.model = self._pick_model(config.models)
        self.perfil = self.model.perfil

        # BSEC timestamp — ms since boot, starts at random offset
        self._bsec_timestamp = random.randint(5000000, 10000000)
        self._bsec_ts_increment = random.randint(250, 800)  # Real: ~300-700ms between readings

        # Initialize with field-realistic baseline values
        self.current_values: dict[str, float] = {}
        for key in self.telemetry_keys:
            if key in self.ranges:
                r = self.ranges[key]
                self.current_values[key] = round(random.uniform(r.min, r.max), 2)
            elif key in BSEC_RANGES:
                low, high = BSEC_RANGES[key]
                self.current_values[key] = round(random.uniform(low, high), 2)

        # Gas resistance starts in a realistic mid-range
        if "gas_resistance" in self.current_values:
            self.current_values["gas_resistance"] = round(random.uniform(90000, 500000), 2)

        # Battery starts near full (4.0-4.2V like real Wingman)
        if "battery_voltage" in self.current_values:
            self.current_values["battery_voltage"] = round(random.uniform(4.05, 4.20), 2)

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
        self._bsec_timestamp += self._bsec_ts_increment + random.randint(-50, 50)

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

            # Gas index always increments by 1 (like real BSEC)
            if key == "gas_index":
                self.current_values[key] = current + 1
                continue

            # Gas resistance: log-scale random walk with occasional large jumps
            if key == "gas_resistance":
                if current > 0:
                    multiplier = 1 + random.uniform(-0.08, 0.08)
                    # Occasional large jump (BSEC recalibration event)
                    if random.random() < 0.05:
                        multiplier = random.uniform(0.3, 3.0)
                    new_val = current * multiplier
                    new_val = max(low, min(high, new_val))
                else:
                    new_val = random.uniform(90000, 500000)
                self.current_values[key] = round(new_val, 2)
                continue

            # Battery slowly drains (never charges)
            if key == "battery_voltage":
                drain = random.uniform(0, 0.003)
                new_val = current - drain
                new_val = max(low, new_val)
                self.current_values[key] = round(new_val, 2)
                continue

            # General random walk bounded by realistic range
            new_val = current + random.uniform(-drift, drift)
            new_val = max(low, min(high, new_val))
            self.current_values[key] = round(new_val, 2)

        return dict(self.current_values)

    def to_mosquitto_payload(self) -> dict:
        """Generate Mosquitto payload matching real Wingman BSEC field output.

        Payload mirrors the exact format from field devices — keys MUST match
        the TB IoT Gateway converter (direct_mqtt.json) which expects
        PascalCase/mixed-case field names, NOT snake_case:

          BSEC outputs:
            Time_stamp = 7164111
            Temperature = 33.15
            Pressure    = 976.03
            Humidity    = 22.91
            Gas_resist  = 96786.39
            Gas_index   = 0
          >> SerialNumber: 00000000002C
          Voltaje_bateria: 4.17
          model: Nordic
          Perfil: ULP
          Ciclo: 222
          EVT:TX_DONE

        Converter mapping (direct_mqtt.json):
          deviceNameJsonExpression: ${SerialNumber}
          attributes: model, Perfil, Ciclo, Voltaje_bateria
          timeseries: Time_stamp, Temperature, Pressure, Humidity, Gas_resist, Gas_index
        """
        telemetry = self.generate_telemetry()
        return {
            # --- Fields mapped by TB IoT Gateway converter ---
            "Temperature": telemetry.get("temperature", 0),
            "Pressure": telemetry.get("pressure", 0),
            "Humidity": telemetry.get("humidity", 0),
            "Gas_resist": telemetry.get("gas_resistance", 0),
            "Gas_index": int(telemetry.get("gas_index", 0)),
            "Time_stamp": self._bsec_timestamp,
            "SerialNumber": self.serial_number,
            "model": self.model.name,
            "Perfil": self.perfil,
            "Ciclo": self.cycle,
            "Voltaje_bateria": telemetry.get("battery_voltage", 0),
            # --- Extra fields (not mapped by converter, but present in real output) ---
            "dev_eui": self.serial_number.zfill(16).lower(),
            "event": "EVT:TX_DONE",
            "gateway": "gw-lora-0001",
            "lorawan_tx": True,
            "source": "bsec-simulator",
            "class_1_probability": round(random.uniform(0, 15), 2),
            "class_2_probability": round(random.uniform(85, 100), 2),
        }

    def to_chirpstack_uplink(self, application_id: str = "simulator") -> dict:
        """Generate ChirpStack v4 compatible uplink payload."""
        telemetry = self.generate_telemetry()
        now = datetime.now(timezone.utc)
        dev_eui = self.serial_number.zfill(16).lower()

        return {
            "deviceInfo": {
                "devEui": dev_eui,
                "deviceName": self.name,
                "applicationId": application_id,
                "applicationName": "IoT Simulator",
                "deviceProfileName": "BME680 Sensor",
                "tags": {
                    "model": self.model.name,
                    "profile": self.perfil,
                    "source": "bsec-simulator",
                },
            },
            "object": {
                "temperature": telemetry.get("temperature", 0),
                "pressure": telemetry.get("pressure", 0),
                "humidity": telemetry.get("humidity", 0),
                "gas_resistance": telemetry.get("gas_resistance", 0),
                "gas_index": int(telemetry.get("gas_index", 0)),
                "battery_voltage": telemetry.get("battery_voltage", 0),
                "model": self.model.name,
                "profile": self.perfil,
                "cycle": self.cycle,
                "serial_number": self.serial_number,
                "event": "EVT:TX_DONE",
            },
            "time": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "devAddr": f"sim{self.index:05d}",
            "fCnt": self.cycle,
            "fPort": 1,
            "adr": True,
            "confirmed": False,
            "data": "",
        }

    @property
    def chirpstack_topic(self) -> str:
        """ChirpStack-compatible MQTT topic for this device."""
        dev_eui = self.serial_number.zfill(16).lower()
        return f"application/simulator/device/{dev_eui}/event/up"

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
