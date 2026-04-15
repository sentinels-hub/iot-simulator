"""Unit tests for transport payload formats."""

import json
from unittest.mock import MagicMock, patch

from app.models import (
    MosquittoViaNginxConfig,
    MqttProtocol,
    TbDirectConfig,
    TransportMode,
)
from app.transports.mosquitto import MosquittoTransport
from app.transports.tb_direct import TbDirectTransport


class TestMosquittoTransport:
    """Tests for MosquittoTransport (Mode A)."""

    def setup_method(self):
        """Create test config."""
        self.config = MosquittoViaNginxConfig(
            mqtt_host="test.mosquitto.local",
            mqtt_port=443,
            mqtt_use_tls=True,
            mqtt_websocket_path="/mqtt",
            mqtt_protocol=MqttProtocol.WEBSOCKETS,
            client_id="test-client-001",
            mosquitto_topic="gw-lora-0001/bme680",
        )
        self.transport = MosquittoTransport(self.config)

    def test_mosquitto_config_attributes(self):
        """Test that config attributes are set correctly."""
        assert self.transport.config.mqtt_host == "test.mosquitto.local"
        assert self.transport.config.mqtt_port == 443
        assert self.transport.config.mosquitto_topic == "gw-lora-0001/bme680"

    def test_publish_not_connected(self):
        """Test that publish returns False when not connected."""
        result = self.transport.publish({"test": "data"})
        assert result is False

    def test_disconnect_without_connection(self):
        """Test that disconnect handles no connection gracefully."""
        self.transport.disconnect()  # Should not raise


class TestTbDirectTransport:
    """Tests for TbDirectTransport (Mode B)."""

    def setup_method(self):
        """Create test config."""
        self.config = TbDirectConfig(
            tb_host="aiot.sentinels.pro",
            tb_port=443,
            tb_use_tls=True,
            tb_token="test-token-123",
            tb_topic="v1/gateway/telemetry",
        )
        self.transport = TbDirectTransport(self.config)

    def test_tb_config_attributes(self):
        """Test that config attributes are set correctly."""
        assert self.transport.config.tb_host == "aiot.sentinels.pro"
        assert self.transport.config.tb_port == 443
        assert self.transport.config.tb_token == "test-token-123"
        assert self.transport.config.tb_topic == "v1/gateway/telemetry"

    def test_publish_not_connected(self):
        """Test that publish_gateway_telemetry returns False when not connected."""
        result = self.transport.publish_gateway_telemetry(
            gateway_name="gw-iot-direct-ingest",
            devices={
                "BME680_SN_001": [{"ts": 123456789, "values": {"temperature": 22.5}}]
            },
        )
        assert result is False

    def test_disconnect_without_connection(self):
        """Test that disconnect handles no connection gracefully."""
        self.transport.disconnect()  # Should not raise
