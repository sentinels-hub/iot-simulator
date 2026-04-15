"""Unit tests for device factory and telemetry drift."""

import math
from app.devices import SimulatedDevice, create_device_pool
from app.models import (
    DeviceConfig,
    DeviceModelConfig,
    TelemetryConfig,
    TelemetryKeyRange,
)


class TestSimulatedDevice:
    """Tests for SimulatedDevice class."""

    def setup_method(self):
        """Create standard test config."""
        self.device_config = DeviceConfig(
            count=10,
            prefix="BME680_SN_",
            serial_prefix="0000000000",
            models=[
                DeviceModelConfig(name="Nordic", perfil="ULP", weight=0.8),
                DeviceModelConfig(name="ESP32", perfil="standard", weight=0.2),
            ],
        )
        self.telemetry_config = TelemetryConfig(
            interval_seconds=30,
            keys=[
                "temperature",
                "pressure",
                "humidity",
                "gas_resistance",
                "gas_index",
                "battery_voltage",
            ],
            ranges={
                "temperature": TelemetryKeyRange(min=15.0, max=50.0, drift=0.5),
                "pressure": TelemetryKeyRange(min=950.0, max=1050.0, drift=1.0),
                "humidity": TelemetryKeyRange(min=10.0, max=95.0, drift=2.0),
                "gas_resistance": TelemetryKeyRange(min=1000.0, max=15000000.0, drift=50000.0),
                "gas_index": TelemetryKeyRange(min=0.0, max=500.0, drift=5.0),
                "battery_voltage": TelemetryKeyRange(min=3.0, max=4.2, drift=0.01),
            },
        )

    def test_device_creation(self):
        """Test that a device is created with correct attributes."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        assert device.name == "BME680_SN_001"
        # Serial format: f"{serial_prefix}{index:X}" = "0000000000" + "1" = "00000000001"
        assert device.serial_number.startswith("0000000000")
        assert device.model.name in ["Nordic", "ESP32"]
        assert device.cycle >= 1

    def test_device_serial_format(self):
        """Test hex serial number format: {serial_prefix}{index:X}."""
        device = SimulatedDevice(
            index=28, config=self.device_config, telemetry_config=self.telemetry_config
        )
        # 28 in hex is 1C
        assert device.serial_number == "0000000000_001C" or "0000000000" in device.serial_number
        # The format should be serial_prefix + index in hex
        expected = f"{self.device_config.serial_prefix}{28:X}"
        assert device.serial_number == expected

    def test_device_pool_size(self):
        """Test that create_device_pool creates the correct number of devices."""
        pool = create_device_pool(self.device_config, self.telemetry_config)
        assert len(pool) == 10

    def test_telemetry_drift_stays_in_range(self):
        """Test that telemetry values stay within configured ranges."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        for _ in range(100):
            values = device.generate_telemetry()
            assert (
                self.telemetry_config.ranges["temperature"].min
                <= values["temperature"]
                <= self.telemetry_config.ranges["temperature"].max
            )
            assert (
                self.telemetry_config.ranges["pressure"].min
                <= values["pressure"]
                <= self.telemetry_config.ranges["pressure"].max
            )
            assert (
                self.telemetry_config.ranges["humidity"].min
                <= values["humidity"]
                <= self.telemetry_config.ranges["humidity"].max
            )
            assert (
                self.telemetry_config.ranges["gas_index"].min
                <= values["gas_index"]
                <= self.telemetry_config.ranges["gas_index"].max
            )

    def test_gas_resistance_log_scale_drift(self):
        """Test that gas_resistance uses log-scale drift (multiply by 0.95-1.05)."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        # Initialize at a known value
        device.current_values["gas_resistance"] = 100000.0
        # Generate many values — should stay proportional, not linear
        prev = 100000.0
        for _ in range(50):
            values = device.generate_telemetry()
            ratio = values["gas_resistance"] / prev if prev > 0 else 1
            # Log-scale drift means ratio should be roughly 0.95 to 1.05
            assert 0.9 <= ratio <= 1.1, f"Ratio {ratio} outside expected range for log-scale drift"
            prev = values["gas_resistance"]

    def test_battery_voltage_only_drains(self):
        """Test that battery_voltage only decreases, never charges."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        initial_voltage = device.current_values["battery_voltage"]
        for _ in range(100):
            values = device.generate_telemetry()
            # Battery should never exceed initial value (it only drains)
            assert (
                values["battery_voltage"] <= initial_voltage + 0.01
            )  # Small tolerance for initial variation
            assert values["battery_voltage"] >= 3.0  # Never below minimum

    def test_mosquitto_payload_format(self):
        """Test Mosquitto payload has correct BSEC field names."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        payload = device.to_mosquitto_payload()
        assert "SerialNumber" in payload
        assert "Temperature" in payload
        assert "Pressure" in payload
        assert "Humidity" in payload
        assert "Gas_resist" in payload
        assert "Gas_index" in payload
        assert "Time_stamp" in payload
        assert "Voltaje_bateria" in payload
        assert "model" in payload
        assert "Perfil" in payload
        assert "Ciclo" in payload
        assert isinstance(payload["Time_stamp"], int)

    def test_tb_values_format(self):
        """Test ThingsBoard values dict has correct field names."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        values = device.to_tb_values()
        assert "temperature" in values
        assert "pressure" in values
        assert "humidity" in values
        assert "gasResistance" in values
        assert "gasIndex" in values
        assert "batteryVoltage" in values

    def test_cycle_increments(self):
        """Test that cycle counter increments with each telemetry generation."""
        device = SimulatedDevice(
            index=1, config=self.device_config, telemetry_config=self.telemetry_config
        )
        initial_cycle = device.cycle
        device.generate_telemetry()
        assert device.cycle == initial_cycle + 1
        device.generate_telemetry()
        assert device.cycle == initial_cycle + 2

    def test_device_model_weighting(self):
        """Test that device model selection follows weight distribution (statistical)."""
        # Create many devices and check model distribution is roughly correct
        config = DeviceConfig(
            count=500,
            prefix="TEST_",
            serial_prefix="000000",
            models=[
                DeviceModelConfig(name="Nordic", perfil="ULP", weight=0.8),
                DeviceModelConfig(name="ESP32", perfil="standard", weight=0.2),
            ],
        )
        pool = create_device_pool(config, self.telemetry_config)
        nordic_count = sum(1 for d in pool if d.model.name == "Nordic")
        esp32_count = sum(1 for d in pool if d.model.name == "ESP32")
        # Allow 15% tolerance for randomness (500 devices, 80/20 split)
        assert 340 < nordic_count < 460, f"Nordic count {nordic_count} outside expected range"
        assert 40 < esp32_count < 160, f"ESP32 count {esp32_count} outside expected range"
